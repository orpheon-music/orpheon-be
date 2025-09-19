import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

import redis
import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import UUID5

from app.config.database import check_database_connection
from app.config.logging import setup_logging
from app.config.ml_service import (
    connect_ml_service,
    disconnect_ml_service,
)
from app.config.rabbit_mq import (
    connect_rabbit_mq,
    disconnect_rabbit_mq,
)
from app.config.redis import (
    check_redis_connection,
    close_redis_connection,
)
from app.config.s3 import get_s3_client
from app.config.settings import get_settings
from app.dto.audio_processing_dto import (
    CreateAudioProcessingRequest,
    CreateAudioProcessingResponse,
    GetAudioProcessingByIdQuery,
    GetAudioProcessingByIdResponse,
    GetAudioProcessingsQuery,
    GetAudioProcessingsResponse,
    UpdateAudioProcessingQuery,
    UpdateAudioProcessingRequest,
    UpdateAudioProcessingResultParams,
    UpdateAudioProcessingResultRequest,
    UpdateAudioProcessingStageParams,
    UpdateAudioProcessingStageRequest,
)
from app.dto.auth_dto import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from app.infra.external_services.rabbit_mq_service import (
    AsyncAudioConsumer,
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
    settings = get_settings()
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
    try:
        await connect_rabbit_mq()
        logger.info("RabbitMQ connection established")
    except Exception as e:
        logger.error(f"RabbitMQ connection error: {e}")

    if settings.ML_SERVICE_ENABLED:
      # Check ML Service connection
      try:
          await connect_ml_service()
          logger.info("ML Service connection established")
      except Exception as e:
          logger.error(f"ML Service connection error: {e}")


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

    # Disconnect from ML Service
    if settings.ML_SERVICE_ENABLED:
      try:
          await disconnect_ml_service()
          logger.info("Disconnected from ML Service")
      except Exception as e:
          logger.warning(f"ML Service disconnect error: {e}")

    # Disconnect from RabbitMQ
    await disconnect_rabbit_mq()
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


# api key middleware
async def api_key_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    settings = get_settings()
    api_key = request.headers.get("X-API-KEY")

    if not api_key or api_key != f"Key {settings.API_KEY}":
        return Response(
            content="Unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    response = await call_next(request)
    return response


@app.middleware("http")
async def log_request_duration(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = (time.perf_counter() - start_time) * 1000  # in ms

    logger.info(
        "%s - %s %s - %d - %.2f ms",
        request.client.host if request.client else "unknown ip",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


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
    reference_url: Annotated[str, Form()],
    is_denoise: Annotated[bool, Form()],
    is_autotune: Annotated[bool, Form()],
    instrument_file: Annotated[UploadFile | None, File()] = None,
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
        is_denoise=is_denoise,
        is_autotune=is_autotune,
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


@app.put(
    "/api/v1/audio-processing/{audio_processing_id}/result",
    tags=["Audio Processing"],
    summary="Update Audio Processing Result Files",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_audio_processing_result_files(
    audio_processing_id: UUID5,
    standard_file: Annotated[UploadFile, File()],
    dynamic_file: Annotated[UploadFile, File()],
    smooth_file: Annotated[UploadFile, File()],
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
    # _api_key_check: Response = Depends(api_key_middleware),
):
    req = UpdateAudioProcessingResultRequest(
        standard_file=standard_file,
        dynamic_file=dynamic_file,
        smooth_file=smooth_file,
    )

    params = UpdateAudioProcessingResultParams(
        audio_processing_id=audio_processing_id,
    )

    await audio_processing_svc.update_audio_processing_result(
        req=req,
        params=params,
    )

    return


@app.put(
    "/api/v1/audio-processing/{audio_processing_id}/stage",
    tags=["Audio Processing"],
    summary="Update Audio Processing Stage",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_audio_processing_stage(
    audio_processing_id: UUID5,
    req: UpdateAudioProcessingStageRequest,
    audio_processing_svc: AudioProcessingService = Depends(
        get_audio_processing_service
    ),
    # _api_key_check: Response = Depends(api_key_middleware),
):
    params = UpdateAudioProcessingStageParams(
        audio_processing_id=audio_processing_id,
    )

    await audio_processing_svc.update_audio_processing_stage(
        params=params,
        req=req,
    )

    return


@app.post(
    "/api/v1/files/download",
    tags=["Files"],
    summary="Download File",
    status_code=status.HTTP_200_OK,
)
async def download_file(
    url: str,
    s3_service: S3Service = Depends(get_s3_client),
):
    logger.info(f"Downloading file: {url}")
    try:
        # Parse the URL to get bucket and file name
        if not url.startswith("https://") and not url.startswith("http://"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL format. Must start with http:// or https://",
            )

        bucket = "ahargunyllib-s3-testing"  # Assuming a fixed bucket for this example
        file_name = url.split("/")[-1]  # Extract file name from URL

        file_content = await s3_service.download_file(bucket, file_name)
        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in S3 bucket.",
            )

        media_type = "application/octet-stream"
        if file_name.endswith(".wav"):
            media_type = "audio/wav"
        elif file_name.endswith(".mp3"):
            media_type = "audio/mpeg"
        elif file_name.endswith(".flac"):
            media_type = "audio/flac"

        return StreamingResponse(
            file_content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_name}"},
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.warning(f"Error downloading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file from S3.",
        ) from e


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
