import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.auth.model import User
from app.domain.role.model import Role, user_roles
from app.domain.permission.model import Permission, role_permissions


@pytest_asyncio.fixture
async def admin_user_with_role_permissions(db_session: AsyncSession) -> tuple[int, str]:
    """Create admin user with role management permissions and return user_id + password."""
    # Create required permissions
    permissions_data = [
        {"code": "role:create", "description": "Create roles"},
        {"code": "role:read", "description": "Read roles"},
        {"code": "role:update", "description": "Update roles"},
        {"code": "role:delete", "description": "Delete roles"},
    ]
    
    perm_ids = []
    for perm_data in permissions_data:
        perm = Permission(**perm_data)
        db_session.add(perm)
        await db_session.flush()
        perm_ids.append(perm.id)
    
    # Create role
    role = Role(name="role_admin", description="Role Administrator")
    db_session.add(role)
    await db_session.flush()
    role_id = role.id
    
    # Assign permissions to role
    for perm_id in perm_ids:
        await db_session.execute(
            insert(role_permissions).values(role_id=role_id, permission_id=perm_id)
        )
    
    # Create user
    password = "admin123"
    user = User(
        first_name="Role",
        last_name="Admin",
        email="roleadmin@example.com",
        password=hash_password(password),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    user_id = user.id
    
    # Assign role to user
    await db_session.execute(
        insert(user_roles).values(user_id=user_id, role_id=role_id)
    )
    
    await db_session.commit()
    return user_id, password


@pytest_asyncio.fixture
async def auth_headers(
    client: AsyncClient, admin_user_with_role_permissions: tuple[int, str]
) -> dict:
    _, password = admin_user_with_role_permissions
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "roleadmin@example.com", "password": password},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_permission(db_session: AsyncSession) -> Permission:
    perm = Permission(code="test:perm", description="Test Permission")
    db_session.add(perm)
    await db_session.commit()
    await db_session.refresh(perm)
    return perm


@pytest.mark.asyncio
class TestCreateRole:
    async def test_create_role_success(
        self, client: AsyncClient, auth_headers: dict, sample_permission: Permission
    ):
        response = await client.post(
            "/api/v1/roles",
            json={
                "name": "new_role",
                "description": "A new role",
                "permissions": [sample_permission.code],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new_role"
        assert sample_permission.code in data["permissions"]

    async def test_create_role_duplicate_name(self, client: AsyncClient, auth_headers: dict):
        # First creation
        await client.post(
            "/api/v1/roles",
            json={"name": "duplicate_role"},
            headers=auth_headers,
        )
        # Second creation attempt
        response = await client.post(
            "/api/v1/roles",
            json={"name": "duplicate_role"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_create_role_invalid_permission(self, client: AsyncClient, auth_headers: dict):
        response = await client.post(
            "/api/v1/roles",
            json={"name": "invalid_perm_role", "permissions": ["non-existent"]},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Invalid permission" in response.json()["detail"]


@pytest.mark.asyncio
class TestGetRole:
    async def test_get_role_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        role = Role(name="test_get_role", description="Test role")
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)

        response = await client.get(f"/api/v1/roles/{role.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == "test_get_role"

    async def test_get_role_not_found(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/roles/99999", headers=auth_headers)
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListRoles:
    async def test_list_roles_success(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/v1/roles", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1  # Should find at least the admin role


@pytest.mark.asyncio
class TestUpdateRole:
    async def test_update_role_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        sample_permission: Permission,
    ):
        role = Role(name="update_me", description="Old description")
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)

        response = await client.put(
            f"/api/v1/roles/{role.id}",
            json={
                "name": "fixed_name",
                "description": "New description",
                "permissions": [sample_permission.code],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "fixed_name"
        assert data["description"] == "New description"
        assert sample_permission.code in data["permissions"]

    async def test_partial_update_role_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        role = Role(name="patch_me")
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)

        response = await client.patch(
            f"/api/v1/roles/{role.id}",
            json={"description": "Patched description"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Patched description"


@pytest.mark.asyncio
class TestDeleteRole:
    async def test_delete_role_success(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        role = Role(name="delete_me")
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)

        response = await client.delete(f"/api/v1/roles/{role.id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deletion
        response = await client.get(f"/api/v1/roles/{role.id}", headers=auth_headers)
        assert response.status_code == 404
