from datetime import UTC, datetime

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
from app.core.security import hash_token, verify_password
from app.domain.auth.exceptions import AuthenticationError
from app.domain.auth.model import Permission, RefreshToken, User

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
        user = await AuthService._get_active_user(db, email)
        await AuthService._check_lockout_status(redis, user)

        if not verify_password(password, user.password):
            await AuthService._handle_failed_password(redis, user)

        if user.mfa_enabled:
            await AuthService._verify_mfa(redis, user, mfa_code)

        # Success: clear failed attempts and issue tokens
        await redis.delete(f"failed_login:{user.email}")
        logger.info("user_authenticated", user_id=user.id, email=email)

        return await AuthService._issue_tokens(db, user)

    @staticmethod
    async def _get_active_user(db: AsyncSession, email: str) -> User:
        """Fetch and validate active user."""
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning("authentication_failed", email=email, reason="user_not_found")
            raise AuthenticationError("Invalid credentials")

        if not user.is_active:
            logger.warning("inactive_account_attempt", email=email, user_id=user.id)
            raise AuthenticationError("Account is disabled. Contact support.")

        return user

    @staticmethod
    async def _check_lockout_status(redis: Redis, user: User) -> None:
        """Check if account is temporarily locked."""
        for key in [f"failed_login:{user.email}", f"failed_mfa:{user.id}"]:
            attempts = int(await redis.get(key) or 0)
            if attempts >= MAX_FAILED_ATTEMPTS:
                logger.warning("account_temporarily_locked", user_id=user.id, attempts=attempts)
                raise AuthenticationError(
                    "Account temporarily locked due to multiple failed attempts. Try again later."
                )

    @staticmethod
    async def _handle_failed_password(redis: Redis, user: User) -> None:
        """Track and handle password failures."""
        login_key = f"failed_login:{user.email}"
        attempts = await redis.incr(login_key)
        await redis.expire(login_key, ATTEMPTS_WINDOW_SECONDS)

        if attempts >= MAX_FAILED_ATTEMPTS:
            logger.warning("account_temporarily_locked", user_id=user.id, attempts=attempts)
            raise AuthenticationError(
                "Account temporarily locked due to multiple failed attempts. Try again later."
            )

        logger.warning("authentication_failed", user_id=user.id, reason="invalid_password")
        raise AuthenticationError("Invalid credentials")

    @staticmethod
    async def _verify_mfa(redis: Redis, user: User, mfa_code: str | None) -> None:
        """Verify MFA code and handle failures."""
        if not mfa_code:
            logger.info("mfa_required", user_id=user.id)
            raise AuthenticationError("MFA code required", mfa_required=True)

        if not MFAService.verify_code(user.mfa_secret, mfa_code):
            mfa_key = f"failed_mfa:{user.id}"
            attempts = await redis.incr(mfa_key)
            await redis.expire(mfa_key, ATTEMPTS_WINDOW_SECONDS)

            if attempts >= MAX_FAILED_ATTEMPTS:
                logger.warning("account_locked_mfa_failures", user_id=user.id, attempts=attempts)
                raise AuthenticationError(
                    "Account temporarily locked due to multiple failed MFA attempts. Try again later."
                )

            logger.warning("mfa_verification_failed", user_id=user.id, attempts=attempts)
            raise AuthenticationError("Invalid MFA code")

        await redis.delete(f"failed_mfa:{user.id}")
        logger.info("mfa_verified", user_id=user.id)

    @staticmethod
    async def _issue_tokens(db: AsyncSession, user: User) -> dict:
        """Generate and store new tokens."""
        access_token = create_access_token(user.id)
        refresh_token_value = create_refresh_token_value()

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
            "token_type": "bearer",  # nosec B105
        }

    @staticmethod
    async def refresh_access_token(
        db: AsyncSession,
        refresh_token_value: str,
    ) -> dict:
        """Rotate refresh token and issue new access token."""
        # Find matching token by its fast hash
        target_hash = hash_token(refresh_token_value)
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == target_hash,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        matching_token = result.scalar_one_or_none()

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
            "token_type": "bearer",  # nosec B105
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

    @staticmethod
    async def list_permissions(db: AsyncSession) -> list[Permission]:
        """Fetch all available permissions from the system."""
        result = await db.execute(select(Permission).order_by(Permission.code))
        return list(result.scalars().all())
