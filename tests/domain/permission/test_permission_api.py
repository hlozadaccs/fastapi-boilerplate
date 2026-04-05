import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.domain.auth.model import User
from app.domain.role.model import Role
from app.domain.permission.model import Permission


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password=hash_password("password123"),
        is_active=True,
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Regular",
        last_name="User",
        email="regular@example.com",
        password=hash_password("password123"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
class TestPermissionsAPI:
    async def test_list_permissions_admin_success(self, client: AsyncClient, admin_user: User):
        # Login to get token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "password123"},
        )
        token = login_resp.json()["access_token"]

        # List permissions
        response = await client.get(
            "/api/v1/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "code" in data[0]
            assert "description" in data[0]

    async def test_list_permissions_regular_user_forbidden(self, client: AsyncClient, regular_user: User):
        # Login to get token
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "regular@example.com", "password": "password123"},
        )
        token = login_resp.json()["access_token"]

        # List permissions
        response = await client.get(
            "/api/v1/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    async def test_list_permissions_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/v1/permissions")
        assert response.status_code == 401
