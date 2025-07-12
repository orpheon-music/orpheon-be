from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.model.user_model import User


class UserRepository:
    def __init__(
        self,
        engine: AsyncEngine,
        async_session_factory: async_sessionmaker[AsyncSession],
    ):
        self.engine = engine
        self.async_session = async_session_factory

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        query = text("""
            SELECT * FROM users WHERE id = :user_id
                     """)

        async with self.async_session() as session:
            result = await session.execute(query, {"user_id": user_id})
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

        async with self.async_session() as session:
            result = await session.execute(query, {"email": email})
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

        async with self.async_session() as session:
            result = await session.execute(
                query,
                {
                    "id": user.id,
                    "email": user.email,
                    "password": user.password,
                    "name": user.name,
                },
            )
            await session.commit()
            return result.scalar_one()
