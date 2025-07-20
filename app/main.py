import asyncio
import os
from io import BytesIO
from typing import Annotated

import uvicorn
import yt_dlp
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config.database import AsyncSessionLocal, engine
from app.dto.audio_processing_dto import (
    CreateAudioProcessingRequest,
    CreateAudioProcessingResponse,
    GetAudioProcessingsQuery,
    GetAudioProcessingsResponse,
)
from app.dto.auth_dto import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.infra.external_services.s3_service import S3Service
from app.repository.user_repository import UserRepository
from app.service.audio_processing_service import AudioProcessingService
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

s3_service = S3Service()

user_repo = UserRepository(
    engine=engine,
    async_session_factory=AsyncSessionLocal,
)

auth_svc = AuthService(user_repository=user_repo)
audio_processing_svc = AudioProcessingService(user_repository=user_repo)

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


@app.get(
    "/api/v1/audio-processing/library",
    tags=["Audio Processing"],
    summary="Get Audio Processing Library",
    response_model=GetAudioProcessingsResponse,
)
async def get_audio_processing_library(
    query: Annotated[GetAudioProcessingsQuery, Depends()],
    current_user: UserResponse = Depends(get_current_user),
):
    """Fetch audio processing library with pagination."""
    return await audio_processing_svc.get_library(query, current_user.id)


@app.post(
    "/api/v1/audio-processing",
    tags=["Audio Processing"],
    summary="Create Audio Processing",
    response_model=CreateAudioProcessingResponse,
)
async def create_audio_processing(
    voice_file: Annotated[UploadFile, File()],
    instrument_file: Annotated[UploadFile, File()],
    reference_url: Annotated[str, File()],
    current_user: UserResponse = Depends(get_current_user),
):
    req = CreateAudioProcessingRequest(
        voice_file=voice_file,
        instrument_file=instrument_file,
        reference_url=reference_url,
        user_id=current_user.id,
    )

    return audio_processing_svc.process_audio(req)


@app.post(
    "/api/v1/files/upload",
    tags=["Files"],
    summary="Upload File",
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(file: Annotated[UploadFile, File()]):
    data = await file.read()
    print(f"Received file: {file.filename}, size: {len(data)} bytes")
    file_content = BytesIO(data)
    if not file_content:
        return {"error": "No file content provided"}
    file_name = file.filename or "uploaded_file"
    bucket = "ahargunyllib-s3-testing"
    file_url = await s3_service.upload_file(file_content, file_name, bucket)
    return {"file_url": file_url}


class DownloadYTRequest(BaseModel):
    url: str


# Blocking function to run in a thread
def download_audio(url: str, output_dir: str = "/tmp") -> str:
    params = {  # type: ignore
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": f"{output_dir}/%(title)s-%(id)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(params) as ydl:  # type: ignore
        info = ydl.extract_info(url, download=True)
        # Get the actual file path of the post-processed file
        file_path = info["requested_downloads"][0]["filepath"]  # type: ignore
        return file_path  # type: ignore


@app.post(
    "/api/v1/download-yt-audio",
    tags=["Files"],
    summary="Download YouTube Audio",
    status_code=status.HTTP_201_CREATED,
)
async def download_youtube_audio(
    req: DownloadYTRequest,
):
    url = req.url.strip()
    print(f"Received YouTube URL: {url}")

    try:
        # Run blocking yt_dlp in thread pool
        file_path = await asyncio.to_thread(download_audio, url)
    except Exception as e:
        print(f"Error downloading audio: {e}")
        raise HTTPException(
            status_code=400, detail="Failed to download audio from YouTube."
        ) from e

    # Upload to S3
    bucket = "ahargunyllib-s3-testing"
    try:
        with open(file_path, "rb") as f:
            file_content = BytesIO(f.read())

        file_name = os.path.basename(file_path)
        file_url = await s3_service.upload_file(file_content, file_name, bucket)
    finally:
        # Always clean up
        try:
            os.remove(file_path)
        except Exception as cleanup_error:
            print(f"Warning: failed to delete local file {file_path}: {cleanup_error}")

    return {"file_url": file_url}


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
