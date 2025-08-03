import asyncio
import os
import uuid
from io import BytesIO
from typing import Annotated, Literal
from uuid import uuid5

import redis
import uvicorn
import yt_dlp
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import UUID5, BaseModel

from app.config.database import check_database_connection
from app.config.logging import setup_logging
from app.config.redis import (
    check_redis_connection,
    close_redis_connection,
)
from app.config.s3 import get_s3_client
from app.dto.audio_processing_dto import (
    CreateAudioProcessingRequest,
    CreateAudioProcessingResponse,
    GetAudioProcessingByIdQuery,
    GetAudioProcessingByIdResponse,
    GetAudioProcessingsQuery,
    GetAudioProcessingsResponse,
    UpdateAudioProcessingQuery,
    UpdateAudioProcessingRequest,
)
from app.dto.auth_dto import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.infra.external_services.rabbit_mq_service import (
    AsyncAudioConsumer,
    RabbitMQService,
)
from app.infra.external_services.s3_service import S3Service
from app.service.audio_processing_service import (
    AudioProcessingService,
    get_audio_processing_service,
)
from app.service.auth_service import AuthService, get_auth_service

logger = setup_logging()


# Background task to run consumer
async def start_background_consumer():
    """Start consumer in background task"""
    consumer = AsyncAudioConsumer()
    try:
        logger.info("Starting background consumer...")
        await consumer.start_consuming()
    except Exception as e:
        logger.error(f"Background consumer error: {e}")
    finally:
        await consumer.stop_consuming()


# Lifespan context manager
@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    # Startup
    logger.info("Starting Orpheon BE...")

    # Check db connection
    try:
        await check_database_connection()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection error: {e}")

    # Check redis connection
    try:
        await check_redis_connection()
        logger.info("Redis connection established")
    except redis.ConnectionError as e:  # type: ignore
        logger.error(f"Redis connection error: {e}")

    # Check RabbitMQ connection
    app.state.queue_service = RabbitMQService()
    try:
        await app.state.queue_service.connect()
        logger.info("RabbitMQ connection established")
    except Exception as e:
        logger.error(f"RabbitMQ connection error: {e}")

    # Check S3 Bucket
    try:
        s3_service: S3Service = get_s3_client()  # type: ignore

        kwargs = {
            "Bucket": "ahargunyllib-s3-testing",
        }

        s3_service.client.head_bucket(**kwargs)

        logger.info("S3 connection established")
    except Exception as e:
        logger.error(f"S3 connection error: {e}")

    # Start background consumer
    consumer_task = asyncio.create_task(start_background_consumer())
    app.state.consumer_task = consumer_task

    yield

    # Shutdown
    # Cancel consumer task
    if hasattr(app.state, "consumer_task"):
        app.state.consumer_task.cancel()
        try:
            await app.state.consumer_task
        except asyncio.CancelledError:
            pass
        logger.info("Background consumer stopped")

    # Disconnect from RabbitMQ
    if hasattr(app.state, "queue_service"):
        await app.state.queue_service.disconnect()
        logger.info("Disconnected from RabbitMQ")

    # Close Redis connection
    await close_redis_connection()
    logger.info("Redis connection closed")

    logger.info("Orpheon BE shutdown complete")


app = FastAPI(
    title="Orpheon BE",
    description="Backend service for Orpheon",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(
    scheme_name="Bearer",
    description="Bearer token authentication for API endpoints",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_svc: AuthService = Depends(get_auth_service),
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
async def register_user(
    req: RegisterRequest,
    auth_svc: AuthService = Depends(get_auth_service),
) -> None:
    return await auth_svc.register_user(req)


@app.post(
    "/api/v1/auth/login",
    tags=["Auth"],
    summary="User Login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
)
async def login_user(
    req: LoginRequest, auth_svc: AuthService = Depends(get_auth_service)
):
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
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
):
    """Fetch audio processing library with pagination."""
    return await audio_processing_svc.get_library(query, current_user.id)


@app.get(
    "/api/v1/audio-processing/{audio_processing_id}",
    tags=["Audio Processing"],
    summary="Get Audio Processing by ID",
    response_model=GetAudioProcessingByIdResponse,
)
async def get_audio_processing_by_id(
    audio_processing_id: UUID5,
    _current_user: UserResponse = Depends(get_current_user),
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
):
    query = GetAudioProcessingByIdQuery(
        audio_processing_id=audio_processing_id,
    )

    res = await audio_processing_svc.get_audio_processing_by_id(query)

    return res


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
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
):
    req = CreateAudioProcessingRequest(
        voice_file=voice_file,
        instrument_file=instrument_file,
        reference_url=reference_url,
        user_id=current_user.id,
    )

    return await audio_processing_svc.process_audio(req)


@app.put(
    "/api/v1/audio-processing/{audio_processing_id}",
    tags=["Audio Processing"],
    summary="Update Audio Processing",
)
async def update_audio_processing(
    audio_processing_id: UUID5,
    manual_file: Annotated[UploadFile | None, File()] = None,
    type: Annotated[Literal["standard", "dynamic", "smooth"] | None, File()] = None,
    _current_user: UserResponse = Depends(get_current_user),
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
):
    if not manual_file and not type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either manual_file or type must be provided.",
        )
    req = UpdateAudioProcessingRequest(
        manual_file=manual_file,
        type=type,
    )

    query = UpdateAudioProcessingQuery(
        audio_processing_id=audio_processing_id,
    )

    await audio_processing_svc.update_audio_processing(
        req=req,
        query=query,
    )

    return


@app.post(
    "/api/v1/files/upload",
    tags=["Files"],
    summary="Upload File",
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: Annotated[UploadFile, File()], s3_service: S3Service = Depends(S3Service)
):
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
    s3_service: S3Service = Depends(S3Service),
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


@app.post(
    "/api/v1/audio-processings/jobs",
    tags=["Audio Processing Jobs"],
    summary="Create Audio Processing Job",
)
async def create_job():
    # Create job
    job_id = uuid5(uuid.NAMESPACE_DNS, "audio_processing_job")

    # Publish to queue
    await app.state.queue_service.publish_job(job_id)

    return {
        "job_id": str(job_id),
    }


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
