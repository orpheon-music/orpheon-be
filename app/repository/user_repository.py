from uuid import UUID

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.model.user_model import User


class UserRepository:
    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        query = text("""
            SELECT * FROM users WHERE id = :user_id
                     """)

        result = await self.db.execute(query, {"user_id": user_id})
        user = result.fetchone()
        if user is None:
            return None

        return User(
            id=user.id,
            email=user.email,
            password=user.password,
            name=user.name,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def get_user_by_email(self, email: str) -> User | None:
        query = text("""
            SELECT * FROM users WHERE email = :email
                     """)

        result = await self.db.execute(query, {"email": email})
        user = result.fetchone()
        if user is None:
            return None

        return User(
            id=user.id,
            email=user.email,
            password=user.password,
            name=user.name,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    async def create_user(self, user: User) -> User:
        query = text("""
            INSERT INTO users (id, email, password, name, created_at, updated_at)
            VALUES (:id, :email, :password, :name, now(), now())
            RETURNING *
                     """)

        result = await self.db.execute(
            query,
            {
                "id": user.id,
                "email": user.email,
                "password": user.password,
                "name": user.name,
            },
        )
        await self.db.commit()
        return result.scalar_one()


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)
