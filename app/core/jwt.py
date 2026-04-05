import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_token(subject: str, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
    }
    encoded: str = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return encoded


def create_access_token(user_id: int) -> str:
    return create_token(
        subject=str(user_id),
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token_value() -> str:
    """Generate a cryptographically secure random refresh token."""
    return secrets.token_urlsafe(32)


def get_refresh_token_expiry() -> datetime:
    """Calculate refresh token expiration datetime."""
    return datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


def decode_token(token: str) -> dict[str, Any]:
    try:
        decoded: dict[str, Any] = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return decoded
    except JWTError as e:
        raise ValueError("Invalid token") from e
