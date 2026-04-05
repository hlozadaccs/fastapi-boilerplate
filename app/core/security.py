import hashlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MB
    parallelism=2,
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    """Hash a refresh token for secure storage using fast deterministic hashing."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(plain_token: str, hashed_token: str) -> bool:
    """Verify a refresh token against its hash."""
    return hash_token(plain_token) == hashed_token
