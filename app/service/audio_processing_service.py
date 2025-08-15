import re
import uuid
from datetime import datetime
from uuid import uuid5

import mutagen.flac as mutagenFLAC
import mutagen.mp3 as mutagenMP3
import mutagen.wave as mutagenWAVE
from fastapi import Depends, HTTPException, status

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
)
from app.dto.pagination_dto import PaginationResponse
from app.infra.external_services.s3_service import S3Service
from app.model.audio_processing_model import AudioProcessing
from app.repository.audio_processing_repository import (
    AudioProcessingRepository,
    get_audio_processing_repository,
)


class AudioProcessingService:
    def __init__(
        self,
        s3_client: S3Service,
        audio_processing_repository: AudioProcessingRepository,
    ):
        self.audio_processing_repository = audio_processing_repository
        self.s3_client = s3_client

    async def process_audio(
        self, req: CreateAudioProcessingRequest
    ) -> CreateAudioProcessingResponse:
        timestamp = datetime.now().isoformat()

        # validate voice_file
        if not req.voice_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Voice file is required",
            )

        # only support .wav, .mp3, .flac
        if req.voice_file.filename and not req.voice_file.filename.endswith(
            (".wav", ".mp3", ".flac")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .wav, .mp3, .flac files are supported",
            )

        # Check if the file size is less than 100MB
        if req.voice_file.size and req.voice_file.size > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 100MB",
            )

        # Check if the file duration is less than 10 minutes
        voice_file_mutagen = None
        if req.voice_file.filename and req.voice_file.filename.endswith(".mp3"):
            voice_file_mutagen = mutagenMP3.Open(req.voice_file.file)
        elif req.voice_file.filename and req.voice_file.filename.endswith(".flac"):
            voice_file_mutagen = mutagenFLAC.Open(req.voice_file.file)
        elif req.voice_file.filename and req.voice_file.filename.endswith(".wav"):
            voice_file_mutagen = mutagenWAVE.Open(req.voice_file.file)

        if (
            voice_file_mutagen and voice_file_mutagen.info.length > 10 * 60  # type: ignore # 10 minutes
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File duration must be less than 10 minutes",
            )

        # validate instrument_file
        if not req.instrument_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Instrument file is required",
            )

        # only support .wav, .mp3, .flac
        if req.instrument_file.filename and not req.instrument_file.filename.endswith(
            (".wav", ".mp3", ".flac")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .wav, .mp3, .flac files are supported",
            )

        # Check if the file size is less than 100MB
        if (
            req.instrument_file.size and req.instrument_file.size > 100 * 1024 * 1024
        ):  # 100MB
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 100MB",
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
            instrument_file_mutagen and instrument_file_mutagen.info.length > 10 * 60  # type: ignore # 10 minutes
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File duration must be less than 10 minutes",
            )

        # validate reference_url
        if not req.reference_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reference URL is required",
            )

        # Check if the reference URL is a valid Youtube URL
        pattern = re.compile(
            r"^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[A-Za-z0-9_-]{11}(&.*)?$"
        )
        if not pattern.match(req.reference_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Youtube URL",
            )

        # Create UUID
        id = uuid5(
            namespace=uuid.NAMESPACE_DNS,
            name=f"{req.user_id}-{timestamp}-{req.voice_file.filename or 'audio'}",
        )

        name = req.voice_file.filename or "audio"
        size = req.voice_file.size or 0
        duration = int(
            voice_file_mutagen.info.length if voice_file_mutagen else 0  # type: ignore
        )
        format = (
            req.voice_file.filename.split(".")[-1]
            if req.voice_file.filename
            else "unknown"
        )
        bitrate: int = voice_file_mutagen.info.bitrate if voice_file_mutagen else 0  # type: ignore

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

        await self.audio_processing_repository.create_audio_processing(audio_processing)

        # Clear cache for the user
        cache_key = f"user:{req.user_id}:audio_processings"
        await self.audio_processing_repository.redis.delete(cache_key)

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
                smooth_audio_url=audio_processing.smooth_audio_url,
            )
        )
        return res

    async def get_library(
        self, query: GetAudioProcessingsQuery, user_id: uuid.UUID
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
            # if audio_processing.standard_audio_url:
            #     standard_audio_url = await self.s3_client.get_presigned_url(
            #         bucket="ahargunyllib-s3-testing",
            #         file_name=audio_processing.standard_audio_url.split("/")[-1],
            #         expiration=8 * 3600,  # 8 hour
            #     )

            dynamic_audio_url = audio_processing.dynamic_audio_url
            # if audio_processing.dynamic_audio_url:
            #     dynamic_audio_url = await self.s3_client.get_presigned_url(
            #         bucket="ahargunyllib-s3-testing",
            #         file_name=audio_processing.dynamic_audio_url.split("/")[-1],
            #         expiration=8 * 3600,  # 8 hour
            #     )

            smooth_audio_url = audio_processing.smooth_audio_url
            # if audio_processing.smooth_audio_url:
            #     smooth_audio_url = await self.s3_client.get_presigned_url(
            #         bucket="ahargunyllib-s3-testing",
            #         file_name=audio_processing.smooth_audio_url.split("/")[-1],
            #         expiration=8 * 3600,  # 8 hour
            #     )

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
                )
            )

        meta = GetAudioProcessingsMeta(pagination=pagination)

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
        # if audio_processing.standard_audio_url:
        #     standard_audio_url = await self.s3_client.get_presigned_url(
        #         bucket="ahargunyllib-s3-testing",
        #         file_name=audio_processing.standard_audio_url.split("/")[-1],
        #         expiration=8 * 3600,  # 8 hour
        #     )

        dynamic_audio_url = audio_processing.dynamic_audio_url
        # if audio_processing.dynamic_audio_url:
        #     dynamic_audio_url = await self.s3_client.get_presigned_url(
        #         bucket="ahargunyllib-s3-testing",
        #         file_name=audio_processing.dynamic_audio_url.split("/")[-1],
        #         expiration=8 * 3600,  # 8 hour
        #     )

        smooth_audio_url = audio_processing.smooth_audio_url
        # if audio_processing.smooth_audio_url:
        #     smooth_audio_url = await self.s3_client.get_presigned_url(
        #         bucket="ahargunyllib-s3-testing",
        #         file_name=audio_processing.smooth_audio_url.split("/")[-1],
        #         expiration=8 * 3600,  # 8 hour
        #     )

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

        # Update the manual audio URL
        audio_processing.manual_audio_url = (
            "https://is3.cloudhost.id/ahargunyllib-s3-testing/manual.wav"
        )

        # Save the updated audio processing
        await self.audio_processing_repository.update_audio_processing(audio_processing)


def get_audio_processing_service(
    s3_client: S3Service = Depends(get_s3_client),
    audio_processing_repository: AudioProcessingRepository = Depends(
        get_audio_processing_repository
    ),
) -> AudioProcessingService:
    return AudioProcessingService(
        s3_client=s3_client,
        audio_processing_repository=audio_processing_repository,
    )
