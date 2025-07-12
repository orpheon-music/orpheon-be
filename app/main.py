import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.database import AsyncSessionLocal, engine
from app.dto.auth_dto import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.repository.user_repository import UserRepository
from app.service.auth_service import AuthService

app = FastAPI(
    title="Orpheon BE",
    description="Backend service for Orpheon",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_repo = UserRepository(
    engine=engine,
    async_session_factory=AsyncSessionLocal,
)

auth_svc = AuthService(user_repository=user_repo)

security = HTTPBearer(
    scheme_name="Bearer",
    description="Bearer token authentication for API endpoints",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    token = credentials.credentials
    return await auth_svc.get_session(token)


@app.get("/", tags=["Root"], summary="Root endpoint")
def read_root():
    return {"message": "Welcome to Orpheon BE!"}


@app.post(
    "/api/v1/auth/register",
    tags=["Auth"],
    summary="User Registration",
    status_code=status.HTTP_201_CREATED,
)
async def register_user(req: RegisterRequest):
    return await auth_svc.register_user(req)


@app.post(
    "/api/v1/auth/login",
    tags=["Auth"],
    summary="User Login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
)
async def login_user(req: LoginRequest):
    return await auth_svc.login_user(req)


@app.get(
    "/api/v1/auth/session",
    tags=["Auth"],
    summary="Check User Session",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
)
async def check_session(
    current_user: UserResponse = Depends(get_current_user),
):
    return current_user


def main():
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
