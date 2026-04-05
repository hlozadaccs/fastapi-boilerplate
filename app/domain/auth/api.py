from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mfa import MFAService
from app.domain.auth.dependencies import get_current_user_id
from app.domain.auth.model import User
from app.domain.auth.schema import (
    LoginRequest,
    MFADisableRequest,
    MFAEnableRequest,
    MFASetupRequest,
    MFASetupResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.domain.auth.service import AuthService
from app.infrastructure.db.dependencies import get_db
from app.infrastructure.redis.client import get_redis

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Authenticate user and issue access + refresh tokens."""
    result = await AuthService.authenticate(
        db, redis, payload.email, payload.password, payload.mfa_code
    )
    await db.commit()
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and issue new access token."""
    return await AuthService.refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all refresh tokens for the authenticated user."""
    await AuthService.revoke_user_tokens(db, user_id)


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    payload: MFASetupRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate MFA secret and QR code for user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA already enabled")

    from app.core.security import verify_password

    if not verify_password(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    # Generate new secret
    secret = MFAService.generate_secret()
    provisioning_uri = MFAService.get_provisioning_uri(secret, user.email)
    qr_code = MFAService.generate_qr_code(provisioning_uri)

    # Store secret temporarily (not enabled yet)
    user.mfa_secret = secret
    await db.commit()

    return MFASetupResponse(
        secret=secret,
        qr_code=qr_code,
        provisioning_uri=provisioning_uri,
    )


@router.post("/mfa/enable", status_code=status.HTTP_204_NO_CONTENT)
async def enable_mfa(
    payload: MFAEnableRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Enable MFA after verifying code."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not set up")

    if user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA already enabled")

    # Verify code
    if not MFAService.verify_code(user.mfa_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    # Enable MFA
    user.mfa_enabled = True
    await db.commit()


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_mfa(
    payload: MFADisableRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA after verifying code."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA not enabled")

    from app.core.security import verify_password

    if not verify_password(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    # Verify code before disabling
    if not MFAService.verify_code(user.mfa_secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid MFA code")

    # Disable MFA
    user.mfa_enabled = False
    user.mfa_secret = None
    await db.commit()
