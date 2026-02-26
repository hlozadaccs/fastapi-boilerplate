from datetime import datetime, UTC

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import (
    create_access_token,
    create_refresh_token_value,
    get_refresh_token_expiry,
)
from app.core.mfa import MFAService
from app.core.security import hash_token, verify_password, verify_token
from app.domain.auth.exceptions import AuthenticationError
from app.domain.auth.model import RefreshToken, User

logger = structlog.get_logger(__name__)

MAX_FAILED_ATTEMPTS = 3
ATTEMPTS_WINDOW_SECONDS = 900  # 15 minutes window to track attempts


class AuthService:
    @staticmethod
    async def authenticate(
        db: AsyncSession,
        redis: Redis,
        email: str,
        password: str,
        mfa_code: str | None = None,
    ) -> dict:
        """Authenticate user and issue tokens."""
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("authentication_failed", email=email, reason="user_not_found")
            raise AuthenticationError("Invalid credentials")

        # Check if account is permanently disabled
        if not user.is_active:
            logger.warning("inactive_account_attempt", email=email, user_id=user.id)
            raise AuthenticationError("Account is disabled. Contact support.")

        if not verify_password(password, user.password):
            # Increment failed attempts in Redis (with TTL window)
            key = f"failed_login:{email}"
            attempts = await redis.incr(key)
            await redis.expire(key, ATTEMPTS_WINDOW_SECONDS)

            if attempts >= MAX_FAILED_ATTEMPTS:
                # Permanently disable account in database
                user.is_active = False
                await db.flush()
                logger.warning(
                    "account_permanently_locked",
                    email=email,
                    user_id=user.id,
                    attempts=attempts,
                )
                raise AuthenticationError("Account locked due to multiple failed attempts. Contact support.")

            logger.warning(
                "authentication_failed",
                email=email,
                reason="invalid_password",
                attempts=attempts,
            )
            raise AuthenticationError("Invalid credentials")

        # Check MFA if enabled
        if user.mfa_enabled:
            if not mfa_code:
                logger.info("mfa_required", user_id=user.id)
                raise AuthenticationError("MFA code required", mfa_required=True)
            
            if not MFAService.verify_code(user.mfa_secret, mfa_code):
                # Track MFA failed attempts
                mfa_key = f"failed_mfa:{user.id}"
                mfa_attempts = await redis.incr(mfa_key)
                await redis.expire(mfa_key, ATTEMPTS_WINDOW_SECONDS)
                
                if mfa_attempts >= MAX_FAILED_ATTEMPTS:
                    user.is_active = False
                    await db.flush()
                    logger.warning(
                        "account_locked_mfa_failures",
                        user_id=user.id,
                        attempts=mfa_attempts,
                    )
                    raise AuthenticationError("Account locked due to multiple failed MFA attempts. Contact support.")
                
                logger.warning("mfa_verification_failed", user_id=user.id, attempts=mfa_attempts)
                raise AuthenticationError("Invalid MFA code")
            
            # Clear MFA attempts on success
            await redis.delete(f"failed_mfa:{user.id}")
            logger.info("mfa_verified", user_id=user.id)

        # Success: clear failed attempts
        await redis.delete(f"failed_login:{email}")
        logger.info("user_authenticated", user_id=user.id, email=email)

        # Generate tokens
        access_token = create_access_token(user.id)
        refresh_token_value = create_refresh_token_value()

        # Store hashed refresh token in database
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token_value),
            expires_at=get_refresh_token_expiry(),
            revoked=False,
        )
        db.add(refresh_token)
        await db.flush()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token_value,
            "token_type": "bearer",
        }

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token_value: str,
    ) -> dict:
        """Rotate refresh token and issue new access token."""
        # Find all non-revoked refresh tokens and check against hash
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        tokens = result.scalars().all()

        # Find matching token by verifying hash
        matching_token = None
        for token in tokens:
            if verify_token(refresh_token_value, token.token_hash):
                matching_token = token
                break

        if not matching_token:
            logger.warning("refresh_token_invalid")
            raise AuthenticationError("Invalid or expired refresh token")

        logger.info("token_refreshed", user_id=matching_token.user_id)

        # Revoke old refresh token (rotation)
        matching_token.revoked = True
        await db.flush()

        # Generate new tokens
        access_token = create_access_token(matching_token.user_id)
        new_refresh_token_value = create_refresh_token_value()

        # Store new refresh token
        new_refresh_token = RefreshToken(
            user_id=matching_token.user_id,
            token_hash=hash_token(new_refresh_token_value),
            expires_at=get_refresh_token_expiry(),
            revoked=False,
        )
        db.add(new_refresh_token)
        await db.flush()

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token_value,
            "token_type": "bearer",
        }

    @staticmethod
    async def revoke_user_tokens(
        db: AsyncSession,
        user_id: int,
    ) -> None:
        """Revoke all active refresh tokens for a user (logout)."""
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await db.flush()
        logger.info("user_logged_out", user_id=user_id)


class PermissionService:
    @staticmethod
    async def get_user_permissions(db: AsyncSession, user_id: int) -> set[str]:
        """Get all effective permissions for a user (from all their roles)."""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return set()

        # Collect all permission codes from all roles
        permissions = set()
        for role in user.roles:
            for permission in role.permissions:
                permissions.add(permission.code)

        return permissions

    @staticmethod
    async def has_permission(db: AsyncSession, user_id: int, permission_code: str) -> bool:
        """Check if user has a specific permission."""
        permissions = await PermissionService.get_user_permissions(db, user_id)
        return permission_code in permissions
