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
