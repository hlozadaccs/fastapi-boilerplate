from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.domain.auth.model import User
from app.domain.user.schema import UserUpdate
from app.infrastructure.db.repository import BaseRepository


class UserService(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    async def create_user(
        self,
        db: AsyncSession,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        is_admin: bool = False,
    ) -> User:
        """Create new user with hashed password."""
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("User already exists")

        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=hash_password(password),
            is_admin=is_admin,
        )

        return await self.create(db, user)

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        payload: UserUpdate,
    ) -> User | None:
        """Update user with validation."""
        user = await self.get_by_id(db, user_id)
        if not user:
            return None

        update_data = payload.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["password"] = hash_password(update_data["password"])

        if "email" in update_data and update_data["email"] != user.email:
            result = await db.execute(select(User).where(User.email == update_data["email"]))
            if result.scalar_one_or_none():
                raise ValueError("Email already exists")

        for key, value in update_data.items():
            setattr(user, key, value)

        await db.flush()
        return user
