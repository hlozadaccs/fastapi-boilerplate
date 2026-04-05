from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.model import Permission


async def ensure_model_permissions(db: AsyncSession, model_name: str) -> list[Permission]:
    """
    Ensure CRUD permissions exist for a model.
    Auto-creates: {model}:create, {model}:read, {model}:update, {model}:delete
    
    Args:
        db: Database session
        model_name: Name of the model (e.g., "user", "product")
    
    Returns:
        List of Permission objects for the model
    """
    actions = ["create", "read", "update", "delete"]
    permissions = []
    
    for action in actions:
        code = f"{model_name}:{action}"
        
        # Check if permission exists
        result = await db.execute(select(Permission).where(Permission.code == code))
        perm = result.scalar_one_or_none()
        
        if not perm:
            # Create permission
            perm = Permission(
                code=code,
                description=f"{action.capitalize()} {model_name}",
            )
            db.add(perm)
        
        permissions.append(perm)
    
    await db.flush()
    return permissions


async def auto_sync_permissions(db: AsyncSession, app=None):
    """
    Introspect SQLAlchemy models and FastAPI routes to automatically generate 
    and purge permissions in the database, similar to Django's post_migrate signals.
    """
    import structlog
    from app.infrastructure.db.base import Base
    from app.domain.auth.model import Permission
    
    logger = structlog.get_logger(__name__)
    
    # Exclude technical models that don't need CRUD permissions
    EXCLUDED_MODELS = {"refreshtoken"}
    
    expected_permissions = set()
    
    # 1. Collect standard CRUD permissions from SQLAlchemy Base Mappers
    for mapper in Base.registry.mappers:
        model_name = mapper.class_.__name__.lower()
        if model_name in EXCLUDED_MODELS:
            continue
        expected_permissions.update({
            f"{model_name}:create",
            f"{model_name}:read",
            f"{model_name}:update",
            f"{model_name}:delete",
        })

    # 2. Collect custom permissions explicitly required by FastAPI Endpoints
    if app:
        def extract_perms(dependant):
            perms = set()
            if not dependant: return perms
            if getattr(dependant.call, "permission_code", None):
                perms.add(dependant.call.permission_code)
            for sub_dep in dependant.dependencies:
                perms.update(extract_perms(sub_dep))
            return perms

        for route in app.routes:
            if hasattr(route, "dependant"):
                expected_permissions.update(extract_perms(route.dependant))

    # 3. Synchronize with Database (Garbage Collection & Insertion)
    result = await db.execute(select(Permission))
    existing_perms = {p.code: p for p in result.scalars().all()}
    
    existing_codes = set(existing_perms.keys())
    
    to_create = expected_permissions - existing_codes
    to_delete = existing_codes - expected_permissions
    
    # Insert missing
    for code in to_create:
        action = code.split(":")[-1]
        model = code.split(":")[0] 
        db.add(Permission(
            code=code, 
            description=f"{action.capitalize()} {model}"
        ))
        
    # Delete orphans (zombies)
    for code in to_delete:
        await db.delete(existing_perms[code])

    await db.commit()
    logger.info(
        "permissions_auto_synced", 
        created=len(to_create), 
        deleted=len(to_delete), 
        total=len(expected_permissions),
    )
