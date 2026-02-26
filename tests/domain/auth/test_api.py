import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.core.security import hash_password
from app.domain.auth.model import User


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Test",
        last_name="User",
        email="test@example.com",
        password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_with_mfa(db_session: AsyncSession) -> User:
    user = User(
        first_name="MFA",
        last_name="User",
        email="mfa@example.com",
        password=hash_password("password123"),
        is_active=True,
        mfa_enabled=True,
        mfa_secret="JBSWY3DPEHPK3PXP",  # Test secret
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user: User):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_email(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "password123"},
        )
        assert response.status_code == 401

    async def test_login_invalid_password(self, client: AsyncClient, test_user: User):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            first_name="Inactive",
            last_name="User",
            email="inactive@example.com",
            password=hash_password("password123"),
            is_active=False,
        )
        db_session.add(user)
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "password123"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_token_success(self, client: AsyncClient, test_user: User):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh_token

    async def test_refresh_token_invalid(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )
        assert response.status_code == 401

    async def test_refresh_token_reuse(self, client: AsyncClient, test_user: User):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestLogout:
    async def test_logout_success(self, client: AsyncClient, test_user: User):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        access_token = login_response.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 204

    async def test_logout_without_token(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401


@pytest.mark.asyncio
class TestMFA:
    async def test_mfa_setup(self, client: AsyncClient, test_user: User):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        access_token = login_response.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/mfa/setup",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "qr_code" in data
        assert "provisioning_uri" in data

    async def test_mfa_enable(self, client: AsyncClient, test_user: User):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        access_token = login_response.json()["access_token"]

        # Setup MFA
        await client.post(
            "/api/v1/auth/mfa/setup",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Mock valid TOTP code
        with patch("app.domain.auth.api.MFAService.verify_code", return_value=True):
            response = await client.post(
                "/api/v1/auth/mfa/enable",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"code": "123456"},
            )
            assert response.status_code == 204

    async def test_mfa_login_requires_code(self, client: AsyncClient, test_user_with_mfa: User):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "mfa@example.com", "password": "password123"},
        )
        assert response.status_code == 401
        # httpx normalizes headers to lowercase
        assert "x-mfa-required" in response.headers or "X-MFA-Required" in response.headers
        assert response.json()["detail"] == "MFA code required"

    async def test_mfa_login_with_valid_code(self, client: AsyncClient, test_user_with_mfa: User):
        with patch("app.domain.auth.service.MFAService.verify_code", return_value=True):
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "mfa@example.com",
                    "password": "password123",
                    "mfa_code": "123456",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "refresh_token" in data

    async def test_mfa_login_with_invalid_code(self, client: AsyncClient, test_user_with_mfa: User):
        with patch("app.domain.auth.service.MFAService.verify_code", return_value=False):
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "mfa@example.com",
                    "password": "password123",
                    "mfa_code": "000000",
                },
            )
            assert response.status_code == 401
            assert "x-mfa-required" not in response.headers and "X-MFA-Required" not in response.headers

    async def test_mfa_login_locks_after_3_failed_attempts(
        self, client: AsyncClient, test_user_with_mfa: User, db_session: AsyncSession, mock_redis
    ):
        # Mock Redis to track attempts
        attempts = {}
        
        async def mock_incr(key):
            attempts[key] = attempts.get(key, 0) + 1
            return attempts[key]
        
        async def mock_expire(key, seconds):
            pass
        
        mock_redis.incr.side_effect = mock_incr
        mock_redis.expire.side_effect = mock_expire
        
        with patch("app.domain.auth.service.MFAService.verify_code", return_value=False):
            # First 2 attempts should fail but not lock
            for _ in range(2):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "mfa@example.com",
                        "password": "password123",
                        "mfa_code": "000000",
                    },
                )
                assert response.status_code == 401
            
            # Third attempt should lock account
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "mfa@example.com",
                    "password": "password123",
                    "mfa_code": "000000",
                },
            )
            assert response.status_code == 401
            assert "locked" in response.json()["detail"].lower()
            
            # Verify account is locked in DB
            await db_session.refresh(test_user_with_mfa)
            assert test_user_with_mfa.is_active is False

    async def test_mfa_disable(self, client: AsyncClient, test_user_with_mfa: User):
        with patch("app.domain.auth.service.MFAService.verify_code", return_value=True):
            login_response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "mfa@example.com",
                    "password": "password123",
                    "mfa_code": "123456",
                },
            )
            access_token = login_response.json()["access_token"]

            response = await client.post(
                "/api/v1/auth/mfa/disable",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"code": "123456"},
            )
            assert response.status_code == 204
