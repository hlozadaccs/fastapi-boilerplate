import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.auth.model import Permission, Role, User, role_permissions, user_roles


@pytest_asyncio.fixture
async def admin_user_with_permissions(db_session: AsyncSession) -> tuple[int, str]:
    """Create admin user with all permissions and return user_id + password."""
    # Create permissions
    permissions_data = [
        {"code": "user:create", "description": "Create users"},
        {"code": "user:read", "description": "Read users"},
        {"code": "user:update", "description": "Update users"},
        {"code": "user:delete", "description": "Delete users"},
    ]
    
    perm_ids = []
    for perm_data in permissions_data:
        perm = Permission(**perm_data)
        db_session.add(perm)
        await db_session.flush()
        perm_ids.append(perm.id)
    
    # Create role
    role = Role(name="admin", description="Administrator")
    db_session.add(role)
    await db_session.flush()
    role_id = role.id
    
    # Assign permissions to role using raw insert
    for perm_id in perm_ids:
        await db_session.execute(
            insert(role_permissions).values(role_id=role_id, permission_id=perm_id)
        )
    
    # Create user
    password = "admin123"
    user = User(
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        password=hash_password(password),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id
    
    # Assign role to user using raw insert
    await db_session.execute(
        insert(user_roles).values(user_id=user_id, role_id=role_id)
    )
    
    await db_session.commit()
    return user_id, password


@pytest_asyncio.fixture
async def auth_headers(
    client: AsyncClient, admin_user_with_permissions: tuple[int, str]
) -> dict:
    user_id, password = admin_user_with_permissions
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestCreateUser:
    async def test_create_user_success(self, client: AsyncClient, auth_headers: dict):
        response = await client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "password": "password123",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["email"] == "john@example.com"
        assert "id" in data

    async def test_create_user_duplicate_email(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.post(
            "/api/v1/users",
            json={
                "first_name": "Test",
                "last_name": "User",
                "email": "admin@example.com",
                "password": "password123",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_create_user_without_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


@pytest.mark.asyncio
class TestGetUser:
    async def test_get_user_success(
        self, client: AsyncClient, auth_headers: dict, admin_user_with_permissions: tuple[int, str]
    ):
        user_id, _ = admin_user_with_permissions
        response = await client.get(f"/api/v1/users/{user_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["email"] == "admin@example.com"

    async def test_get_user_not_found(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/users/99999", headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListUsers:
    async def test_list_users_success(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["total"] >= 1
        assert data["pagination"]["page"] == 1

    async def test_list_users_pagination(self, client: AsyncClient, auth_headers: dict):
        response = await client.get(
            "/api/v1/users?page=1&page_size=5", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 5


@pytest.mark.asyncio
class TestUpdateUser:
    async def test_update_user_success(
        self, client: AsyncClient, auth_headers: dict, admin_user_with_permissions: tuple[int, str]
    ):
        user_id, _ = admin_user_with_permissions
        response = await client.put(
            f"/api/v1/users/{user_id}",
            json={
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"

    async def test_partial_update_user_success(
        self, client: AsyncClient, auth_headers: dict, admin_user_with_permissions: tuple[int, str]
    ):
        user_id, _ = admin_user_with_permissions
        response = await client.patch(
            f"/api/v1/users/{user_id}",
            json={"first_name": "Patched"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Patched"

    async def test_update_user_not_found(self, client: AsyncClient, auth_headers: dict):
        response = await client.put(
            "/api/v1/users/99999",
            json={"first_name": "Test", "last_name": "User", "email": "test@example.com"},
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteUser:
    async def test_delete_user_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        user = User(
            first_name="Delete",
            last_name="Me",
            email="delete@example.com",
            password=hash_password("password123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        response = await client.delete(f"/api/v1/users/{user.id}", headers=auth_headers)
        assert response.status_code == 204

    async def test_delete_user_not_found(self, client: AsyncClient, auth_headers: dict):
        response = await client.delete("/api/v1/users/99999", headers=auth_headers)
        assert response.status_code == 404
