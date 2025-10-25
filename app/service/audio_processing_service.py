import asyncio
import logging
import uuid
from datetime import datetime
from io import BytesIO
from uuid import uuid4, uuid5

import mutagen.flac as mutagenFLAC
import mutagen.mp3 as mutagenMP3
import mutagen.wave as mutagenWAVE
import yt_dlp
from fastapi import Depends, HTTPException, status

from app.config.rabbit_mq import get_rabbit_mq_service
from app.config.s3 import get_s3_client
from app.dto.audio_processing_dto import (
    AudioProcessingResponse,
    CreateAudioProcessingRequest,
    CreateAudioProcessingResponse,
    GetAudioProcessingByIdQuery,
    GetAudioProcessingByIdResponse,
    GetAudioProcessingsMeta,
    GetAudioProcessingsQuery,
    GetAudioProcessingsResponse,
    UpdateAudioProcessingQuery,
    UpdateAudioProcessingRequest,
    UpdateAudioProcessingResultParams,
    UpdateAudioProcessingResultRequest,
    UpdateAudioProcessingStageParams,
    UpdateAudioProcessingStageRequest,
)
from app.dto.pagination_dto import PaginationResponse
from app.infra.external_services.rabbit_mq_service import RabbitMQService
from app.infra.external_services.s3_service import S3Service
from app.model.audio_processing_model import AudioProcessing
from app.repository.audio_processing_repository import (
    AudioProcessingRepository,
    get_audio_processing_repository,
)
from app.repository.feature_event_repository import (
    FeatureEventRepository,
    get_feature_event_repository,
)

logger = logging.getLogger(__name__)


class AudioProcessingService:
    def __init__(
        self,
        s3_client: S3Service,
        audio_processing_repository: AudioProcessingRepository,
        rabbitmq_service: RabbitMQService,
        feature_event_repository: FeatureEventRepository,
    ):
        self.audio_processing_repository = audio_processing_repository
        self.s3_client = s3_client
        self.rabbitmq_service = rabbitmq_service
        self.feature_event_repository = feature_event_repository

    async def process_audio(
        self, req: CreateAudioProcessingRequest
    ) -> CreateAudioProcessingResponse:
        timestamp = datetime.now().isoformat()

        # validate voice_file
        logger.info("Validating voice file")
        if not req.voice_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice file is required",
            )
        logger.info("Voice file provided")

        # only support .wav, .mp3, .flac
        if not req.voice_file.filename.endswith(  # type: ignore
            (".wav", ".mp3", ".flac")
        ):
            logger.warning(f"Unsupported file format: {req.voice_file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .wav, .mp3, .flac files are supported",
            )
        logger.info(f"Voice file format is {req.voice_file.filename.split('.')[-1]}")  # type: ignore

        # Check if the file size is less than 100MB
        if req.voice_file.size > 100 * 1024 * 1024:  # type: ignore # 100MB
            logger.warning(f"File size too large: {req.voice_file.size} bytes")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 100MB",
            )
        logger.info(
            f"Voice file size: {req.voice_file.size} bytes, {req.voice_file.size / (1024 * 1024) if req.voice_file.size else 0:.2f} MB"
        )  # type: ignore

        # Check if the file duration is less than 10 minutes
        voice_file_mutagen = None
        if req.voice_file.filename and req.voice_file.filename.endswith(".mp3"):
            voice_file_mutagen = mutagenMP3.Open(req.voice_file.file)
        elif req.voice_file.filename and req.voice_file.filename.endswith(".flac"):
            voice_file_mutagen = mutagenFLAC.Open(req.voice_file.file)
        elif req.voice_file.filename and req.voice_file.filename.endswith(".wav"):
            voice_file_mutagen = mutagenWAVE.Open(req.voice_file.file)

        if (
            voice_file_mutagen.info.length > 10 * 60  # type: ignore # 10 minutes
        ):
            logger.warning(f"File duration: {voice_file_mutagen.info.length}")  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File duration must be less than 10 minutes",
            )
        logger.info(f"Voice file mutagen duration: {voice_file_mutagen.info.length}")  # type: ignore

        # validate instrument_file
        if req.instrument_file:
            logger.info("Validating instrument file")

            # only support .wav, .mp3, .flac
            if not req.instrument_file.filename.endswith(  # type: ignore
                (".wav", ".mp3", ".flac")
            ):
                logger.warning(
                    f"Unsupported instrument file format: {req.instrument_file.filename}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only .wav, .mp3, .flac files are supported",
                )
            logger.info(
                f"Instrument file format is {req.instrument_file.filename.split('.')[-1]}"  # type: ignore
            )

            # Check if the file size is less than 100MB
            if (
                req.instrument_file.size > 100 * 1024 * 1024  # type: ignore
            ):  # 100MB
                logger.warning(f"Instrument file size: {req.instrument_file.size}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File size must be less than 100MB",
                )
            logger.info(
                f"Instrument file size: {req.instrument_file.size} bytes, {req.instrument_file.size / (1024 * 1024):.2f} MB"  # type: ignore
            )

            # Check if the file duration is less than 10 minutes
            instrument_file_mutagen = None
            if req.instrument_file.filename and req.instrument_file.filename.endswith(
                ".mp3"
            ):
                instrument_file_mutagen = mutagenMP3.Open(req.instrument_file.file)
            elif req.instrument_file.filename and req.instrument_file.filename.endswith(
                ".flac"
            ):
                instrument_file_mutagen = mutagenFLAC.Open(req.instrument_file.file)
            elif req.instrument_file.filename and req.instrument_file.filename.endswith(
                ".wav"
            ):
                instrument_file_mutagen = mutagenWAVE.Open(req.instrument_file.file)

            if (
                instrument_file_mutagen.info.length > 10 * 60  # type: ignore # 10 minutes
            ):
                logger.warning(
                    f"Instrument file duration: {instrument_file_mutagen.info.length}"  # type: ignore
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File duration must be less than 10 minutes",
                )
            logger.info(
                f"Instrument file mutagen duration: {instrument_file_mutagen.info.length}"  # type: ignore
            )

        # validate reference_file
        logger.info("Validating reference file")
        if not req.reference_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reference file is required",
            )
        logger.info("Reference file provided")

        # only support .wav, .mp3, .flac
        if not req.reference_file.filename.endswith(  # type: ignore
            (".wav", ".mp3", ".flac")
        ):
            logger.warning(f"Unsupported file format: {req.reference_file.filename}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .wav, .mp3, .flac files are supported",
            )
        logger.info(
            f"Reference file format is {req.reference_file.filename.split('.')[-1]}"  # type: ignore
        )

        # Check if the file size is less than 100MB
        if req.reference_file.size > 100 * 1024 * 1024:  # type: ignore # 100MB
            logger.warning(f"File size too large: {req.reference_file.size} bytes")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 100MB",
            )
        logger.info(
            f"Reference file size: {req.reference_file.size} bytes, {req.reference_file.size / (1024 * 1024) if req.reference_file.size else 0:.2f} MB"
        )  # type: ignore

        # Check if the file duration is less than 10 minutes
        reference_file_mutagen = None
        if req.reference_file.filename and req.reference_file.filename.endswith(".mp3"):
            reference_file_mutagen = mutagenMP3.Open(req.reference_file.file)
        elif req.reference_file.filename and req.reference_file.filename.endswith(
            ".flac"
        ):
            reference_file_mutagen = mutagenFLAC.Open(req.reference_file.file)
        elif req.reference_file.filename and req.reference_file.filename.endswith(
            ".wav"
        ):
            reference_file_mutagen = mutagenWAVE.Open(req.reference_file.file)

        if (
            reference_file_mutagen.info.length > 10 * 60  # type: ignore # 10 minutes
        ):
            logger.warning(f"File duration: {reference_file_mutagen.info.length}")  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File duration must be less than 10 minutes",
            )
        logger.info(
            f"Reference file mutagen duration: {reference_file_mutagen.info.length}"  # type: ignore
        )

        # Create UUID
        id = uuid5(
            namespace=uuid.NAMESPACE_DNS,
            name=f"{req.user_id}-{timestamp}-{req.voice_file.filename or 'audio'}",
        )

        name = req.voice_file.filename or "audio"
        size = req.voice_file.size or 0
        duration = round(voice_file_mutagen.info.length)  # type: ignore
        format = (
            req.voice_file.filename.split(".")[-1]
            if req.voice_file.filename
            else "unknown"
        )
        bitrate = voice_file_mutagen.info.bitrate  # type: ignore
        logger.info(
            f"Creating audio processing with ID: {id}, Name: {name}, Size: {size}, Duration: {duration}, Format: {format}, Bitrate: {bitrate}"  # type: ignore
        )

        audio_processing = AudioProcessing(
            id=id,
            user_id=req.user_id,
            name=name,
            size=size,
            duration=duration,
            format=format,
            bitrate=bitrate,  # type: ignore
            standard_audio_url=None,
            dynamic_audio_url=None,
            smooth_audio_url=None,
            manual_audio_url=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        logger.info(f"Creating audio processing record with ID: {audio_processing.id}")
        await self.audio_processing_repository.create_audio_processing(audio_processing)
        logger.info("Audio processing record created successfully")

        # Set stage to 0 - Pending
        await self.audio_processing_repository.set_audio_processing_stage(
            audio_processing.id, 0
        )

        req.voice_file.file.seek(0)
        voice_bytes = await req.voice_file.read()
        instrument_bytes = None
        if req.instrument_file:
            req.instrument_file.file.seek(0)
            instrument_bytes = await req.instrument_file.read()
        req.reference_file.file.seek(0)
        reference_bytes = await req.reference_file.read()

        task = asyncio.create_task(
            self._handle_audio_processing(
                voice_bytes,
                instrument_bytes,
                reference_bytes,
                req.is_denoise,
                req.is_autotune,
                audio_processing,
            ),
            name=f"handle-audio-processing-{audio_processing.id}",
        )

        # Surface exceptions for logs:
        task.add_done_callback(lambda t: t.exception())

        # Clear cache for the user
        logger.info("Clearing cache for the user")
        cache_key = f"user:{req.user_id}:audio_processings"
        await self.audio_processing_repository.redis.delete(cache_key)
        logger.info("Cache cleared successfully")

        res = CreateAudioProcessingResponse(
            audio_processing=AudioProcessingResponse(
                id=audio_processing.id,
                user_id=audio_processing.user_id,
                name=audio_processing.name,
                size=audio_processing.size,
                duration=audio_processing.duration,
                format=audio_processing.format,
                bitrate=audio_processing.bitrate,
                standard_audio_url=audio_processing.standard_audio_url,
                dynamic_audio_url=audio_processing.dynamic_audio_url,
                stage=0,
                smooth_audio_url=audio_processing.smooth_audio_url,
                created_at=str(audio_processing.created_at),
                updated_at=str(audio_processing.updated_at),
            )
        )
        return res

    async def _handle_audio_processing(
        self,
        voice_bytes: bytes,
        instrument_bytes: bytes | None,
        reference_bytes: bytes,
        is_denoise: bool,
        is_autotune: bool,
        audio_processing: AudioProcessing,
    ) -> None:
        logger.info("Uploading voice file to S3")
        voice_file_content = BytesIO(voice_bytes)
        voice_file_filename = f"{audio_processing.id}-voice.{audio_processing.format}"  # type: ignore
        voice_file_url = await self.s3_client.upload_file(
            voice_file_content, voice_file_filename, "artylab.dev02"
        )
        logger.info("Voice file uploaded to S3")

        instrument_file_url = None
        if instrument_bytes:
            logger.info("Uploading instrument file to S3")
            instrument_file_content = BytesIO(instrument_bytes)
            instrument_file_filename = (
                f"{audio_processing.id}-instrument.{audio_processing.format}"  # type: ignore
            )
            instrument_file_url = await self.s3_client.upload_file(
                instrument_file_content, instrument_file_filename, "artylab.dev02"
            )
            logger.info("Instrument file uploaded to S3")

        logger.info("Uploading reference file to S3")
        reference_file_content = BytesIO(reference_bytes)
        reference_file_filename = (
            f"{audio_processing.id}-reference.{audio_processing.format}"  # type: ignore
        )
        reference_file_url = await self.s3_client.upload_file(
            reference_file_content, reference_file_filename, "artylab.dev02"
        )
        logger.info("Reference file uploaded to S3")

        additional_data: dict[str, str | bool] = {
            "voice_file_url": voice_file_url,
            "reference_file_url": reference_file_url,
            "is_denoise": is_denoise,
            "is_autotune": is_autotune,
        }
        if instrument_file_url:
            additional_data["instrument_file_url"] = instrument_file_url

        # Publish job to RabbitMQ
        logger.info("Publishing job to RabbitMQ")
        await self.rabbitmq_service.publish_job(
            audio_processing.id,
            "normal",
            additional_data,
        )
        logger.info("Job published to RabbitMQ successfully")

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing",
            event_type="audio_processing_started",
        )

    async def get_library(
        self, query: GetAudioProcessingsQuery, user_id: uuid.UUID | None
    ) -> GetAudioProcessingsResponse:
        """Get audio processing library"""
        audio_processings = (
            await self.audio_processing_repository.get_audio_processings_by_user_id(
                user_id=user_id,
                limit=query.page * 10,  # Assuming 10 items per page
                offset=(query.page - 1) * 10,
            )
        )
        count = (
            await self.audio_processing_repository.count_audio_processings_by_user_id(
                user_id=user_id
            )
        )
        pagination = PaginationResponse(
            page=query.page,
            limit=10,  # Assuming 10 items per page
            total_data=count,
            total_page=(count // 10) + (1 if count % 10 > 0 else 0),
        )
        audio_processings_res: list[AudioProcessingResponse] = []

        for audio_processing in audio_processings:
            standard_audio_url = audio_processing.standard_audio_url
            dynamic_audio_url = audio_processing.dynamic_audio_url
            smooth_audio_url = audio_processing.smooth_audio_url

            stage = 5
            if (
                not audio_processing.smooth_audio_url
                or not audio_processing.dynamic_audio_url
                or not audio_processing.standard_audio_url
            ):
                logger.info(
                    f"Audio processing {audio_processing.id} is missing URLs, checking stage... "
                )
                stageRes = (
                    await self.audio_processing_repository.get_audio_processing_stage(
                        audio_processing.id
                    )
                )
                logger.info(
                    f"Stage for audio processing {audio_processing.id} is {stageRes}"
                )
                if stageRes is not None:
                    stage = stageRes

            audio_processings_res.append(
                AudioProcessingResponse(
                    id=audio_processing.id,
                    user_id=audio_processing.user_id,
                    name=audio_processing.name,
                    size=audio_processing.size,
                    duration=audio_processing.duration,
                    format=audio_processing.format,
                    bitrate=audio_processing.bitrate,
                    standard_audio_url=standard_audio_url,
                    dynamic_audio_url=dynamic_audio_url,
                    smooth_audio_url=smooth_audio_url,
                    stage=stage,
                    created_at=str(audio_processing.created_at),
                    updated_at=str(audio_processing.updated_at),
                )
            )

        meta = GetAudioProcessingsMeta(pagination=pagination)

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing", event_type="audio_processing_listed"
        )

        return GetAudioProcessingsResponse(
            audio_processings=audio_processings_res,
            meta=meta,
        )

    async def get_audio_processing_by_id(
        self, query: GetAudioProcessingByIdQuery
    ) -> GetAudioProcessingByIdResponse:
        """Get audio processing by ID"""
        audio_processing = (
            await self.audio_processing_repository.get_audio_processing_by_id(
                audio_processing_id=query.audio_processing_id
            )
        )
        if not audio_processing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio processing not found",
            )
        # Generate presigned URLs for audio files
        standard_audio_url = audio_processing.standard_audio_url
        dynamic_audio_url = audio_processing.dynamic_audio_url
        smooth_audio_url = audio_processing.smooth_audio_url

        stage = 5
        if (
            not audio_processing.smooth_audio_url
            or not audio_processing.dynamic_audio_url
            or not audio_processing.standard_audio_url
        ):
            stageRes = (
                await self.audio_processing_repository.get_audio_processing_stage(
                    audio_processing.id
                )
            )
            if stageRes:
                stage = stageRes

        audio_processing = AudioProcessingResponse(
            id=audio_processing.id,
            user_id=audio_processing.user_id,
            name=audio_processing.name,
            size=audio_processing.size,
            duration=audio_processing.duration,
            format=audio_processing.format,
            bitrate=audio_processing.bitrate,
            standard_audio_url=standard_audio_url,
            dynamic_audio_url=dynamic_audio_url,
            smooth_audio_url=smooth_audio_url,
            stage=stage,
            created_at=str(audio_processing.created_at),
            updated_at=str(audio_processing.updated_at),
        )

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing",
            event_type="audio_processing_viewed",
            event_data={
                "audio_processing_id": str(audio_processing.id),
            },
        )

        return GetAudioProcessingByIdResponse(audio_processing=audio_processing)

    async def update_audio_processing(
        self, query: UpdateAudioProcessingQuery, req: UpdateAudioProcessingRequest
    ) -> None:
        """Update audio processing with manual file"""
        audio_processing = (
            await self.audio_processing_repository.get_audio_processing_by_id(
                audio_processing_id=query.audio_processing_id
            )
        )
        if not audio_processing:
            raise ValueError("Audio processing not found")

        if req.manual_file:
            # Upload manual file to S3
            manual_file_data = await req.manual_file.read()
            manual_file_content = BytesIO(manual_file_data)
            manual_file_filename = f"{audio_processing.id}-manual.{req.manual_file.filename.split('.')[-1]}"  # type: ignore
            manual_file_url = await self.s3_client.upload_file(
                manual_file_content, manual_file_filename, "artylab.dev02"
            )
            audio_processing.manual_audio_url = manual_file_url

        # Save the updated audio processing
        await self.audio_processing_repository.update_audio_processing(audio_processing)

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing",
            event_type="audio_processing_updated",
            event_data={
                "audio_processing_id": str(audio_processing.id),
            },
        )

    async def update_audio_processing_result(
        self,
        params: UpdateAudioProcessingResultParams,
        req: UpdateAudioProcessingResultRequest,
    ) -> None:
        """Update audio processing with result files from ML service"""
        audio_processing = (
            await self.audio_processing_repository.get_audio_processing_by_id(
                audio_processing_id=params.audio_processing_id
            )
        )
        if not audio_processing:
            raise ValueError("Audio processing not found")

        audio_processing.standard_audio_url = req.standard_file
        audio_processing.dynamic_audio_url = req.dynamic_file
        audio_processing.smooth_audio_url = req.smooth_file

        await self.audio_processing_repository.update_audio_processing(audio_processing)
        logger.info("Audio processing record updated successfully")

        await self.audio_processing_repository.set_audio_processing_stage(
            audio_processing.id, 5
        )

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing",
            event_type="audio_processing_completed",
            event_data={
                "audio_processing_id": str(audio_processing.id),
            },
        )

    async def update_audio_processing_stage(
        self,
        params: UpdateAudioProcessingStageParams,
        req: UpdateAudioProcessingStageRequest,
    ) -> None:
        """Update audio processing stage"""
        audio_processing = (
            await self.audio_processing_repository.get_audio_processing_by_id(
                audio_processing_id=params.audio_processing_id
            )
        )

        if not audio_processing:
            raise ValueError("Audio processing not found")

        await self.audio_processing_repository.set_audio_processing_stage(
            audio_processing.id, req.stage
        )
        logger.info(f"Audio processing stage updated to {req.stage}")

        await self.feature_event_repository.create_feature_event(
            feature_name="audio_processing",
            event_type="audio_processing_stage_updated",
            event_data={
                "stage": str(req.stage),
                "audio_processing_id": str(audio_processing.id),
            },
        )

        return


def get_audio_processing_service(
    s3_client: S3Service = Depends(get_s3_client),
    audio_processing_repository: AudioProcessingRepository = Depends(
        get_audio_processing_repository
    ),
    rabbitmq_service: RabbitMQService = Depends(get_rabbit_mq_service),
    feature_event_repository: FeatureEventRepository = Depends(
        get_feature_event_repository
    ),
) -> AudioProcessingService:
    return AudioProcessingService(
        s3_client=s3_client,
        audio_processing_repository=audio_processing_repository,
        rabbitmq_service=rabbitmq_service,
        feature_event_repository=feature_event_repository,
    )


# # Blocking function to run in a thread
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
