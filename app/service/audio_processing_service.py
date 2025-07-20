import uuid
from datetime import datetime
from uuid import uuid5

from fastapi import HTTPException, status

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
from app.model.audio_processing_model import AudioProcessing
from app.repository.audio_processing_repository import AudioProcessingRepository


class AudioProcessingService:
    def __init__(self, audio_processing_repository: AudioProcessingRepository):
        self.audio_processing_repository = audio_processing_repository

    async def process_audio(
        self, req: CreateAudioProcessingRequest
    ) -> CreateAudioProcessingResponse:
        timestamp = datetime.now().isoformat()

        # Create UUID
        id = uuid5(
            namespace=uuid.NAMESPACE_DNS,
            name=req.voice_file.filename or "audio" + timestamp,
        )

        name = req.voice_file.filename or "audio"
        size = req.voice_file.size or 0
        duration = 0  # Placeholder, actual duration should be calculated
        format = (
            req.voice_file.filename.split(".")[-1]
            if req.voice_file.filename
            else "unknown"
        )
        bitrate = 128  # Placeholder, actual bitrate should be calculated

        audio_processing = AudioProcessing(
            id=id,
            user_id=req.user_id,
            name=name,
            size=size,
            duration=duration,
            format=format,
            bitrate=bitrate,
            standard_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
            dynamic_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/dynamic.wav",
            smooth_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
            manual_audio_url=None,
        )

        await self.audio_processing_repository.create_audio_processing(audio_processing)

        await self.audio_processing_repository.update_audio_processing(audio_processing)

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
        # Placeholder for actual implementation
        # audio_processings = [
        #     AudioProcessingResponse(
        #         id=uuid5(namespace=uuid.NAMESPACE_DNS, name="audio1"),
        #         user_id=uuid.uuid4(),
        #         name="sample-audio1.mp3",
        #         size=1024,
        #         duration=120,
        #         format="mp3",
        #         bitrate=128,
        #         standard_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
        #         dynamic_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/dynamic.wav",
        #         smooth_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
        #     ),
        #     AudioProcessingResponse(
        #         id=uuid5(namespace=uuid.NAMESPACE_DNS, name="audio1"),
        #         user_id=uuid.uuid4(),
        #         name="sample-audio2.mp3",
        #         size=1024,
        #         duration=120,
        #         format="mp3",
        #         bitrate=128,
        #         standard_audio_url=None,
        #         dynamic_audio_url=None,
        #         smooth_audio_url=None,
        #     ),
        # ]

        # pagination = PaginationResponse(
        #     page=1,
        #     limit=10,
        #     total_data=2,
        #     total_page=1,
        # )

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
        audio_processings = [
            AudioProcessingResponse(
                id=ap.id,
                user_id=ap.user_id,
                name=ap.name,
                size=ap.size,
                duration=ap.duration,
                format=ap.format,
                bitrate=ap.bitrate,
                standard_audio_url=ap.standard_audio_url,
                dynamic_audio_url=ap.dynamic_audio_url,
                smooth_audio_url=ap.smooth_audio_url,
            )
            for ap in audio_processings
        ]

        meta = GetAudioProcessingsMeta(pagination=pagination)

        return GetAudioProcessingsResponse(
            audio_processings=audio_processings,
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

        audio_processing = AudioProcessingResponse(
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
