import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid5

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status

from app.config.settings import Settings
from app.dto.auth_dto import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.model.user_model import User
from app.repository.user_repository import UserRepository, get_user_repository


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def register_user(self, user_data: RegisterRequest) -> None:
        """Register new user"""
        # Check if user already exists
        existing_user = await self.user_repository.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        # Hash password
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(user_data.password.encode("utf-8"), salt).decode(
            "utf-8"
        )

        # Create UUID
        id = uuid5(namespace=uuid.NAMESPACE_DNS, name=user_data.email)

        await self.user_repository.create_user(
            User(
                id=id,
                email=user_data.email,
                password=password_hash,
                name=user_data.name,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        return

    async def login_user(self, login_data: LoginRequest) -> LoginResponse:
        """Login user"""
        # Get user by email
        user = await self.user_repository.get_user_by_email(login_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # Verify password
        password_verified = bcrypt.checkpw(
            login_data.password.encode("utf-8"), user.password.encode("utf-8")
        )
        if not password_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        # Create tokens
        settings = Settings()
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRES_IN)
        payload: dict[str, Any] = {"user_id": str(user.id), "exp": expire}  #
        access_token = jwt.encode(  # type: ignore
            payload=payload,
            key=settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )

        return LoginResponse(access_token=access_token)

    async def get_session(self, token: str) -> UserResponse:
        """Get user session from token"""
        settings = Settings()
        payload = jwt.decode(  # type: ignore
            token, settings.JWT_SECRET_KEY, algorithms=["HS256"]
        )

        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        user = await self.user_repository.get_user_by_id(uuid.UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at=user.created_at,
        )


def get_auth_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(user_repository=user_repository)
