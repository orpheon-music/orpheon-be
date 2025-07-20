import uuid
from uuid import uuid5

from app.dto.audio_processing_dto import (
    AudioProcessingResponse,
    CreateAudioProcessingRequest,
    CreateAudioProcessingResponse,
    GetAudioProcessingsMeta,
    GetAudioProcessingsQuery,
    GetAudioProcessingsResponse,
)
from app.dto.pagination_dto import PaginationResponse
from app.repository.user_repository import UserRepository


class AudioProcessingService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def process_audio(
        self, req: CreateAudioProcessingRequest
    ) -> CreateAudioProcessingResponse:
        """Process audio files and return response"""

        # Create UUID
        id = uuid5(
            namespace=uuid.NAMESPACE_DNS, name=req.voice_file.filename or "audio"
        )

        res = CreateAudioProcessingResponse(
            audio_processing=AudioProcessingResponse(
                id=id,
                user_id=req.user_id,
                name=req.voice_file.filename or "audio",
                size=req.voice_file.size
                or 0,  # Placeholder, actual size should be calculated
                duration=0,  # Placeholder, actual duration should be calculated
                format=req.voice_file.content_type or "mp3",
                bitrate=128,  # Placeholder, actual bitrate should be calculated
                standard_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
                dynamic_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/dynamic.wav",
                smooth_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
            )
        )
        return res

    async def get_library(
        self, query: GetAudioProcessingsQuery, user_id: uuid.UUID
    ) -> GetAudioProcessingsResponse:
        """Get audio processing library"""
        # Placeholder for actual implementation
        audio_processings = [
            AudioProcessingResponse(
                id=uuid5(namespace=uuid.NAMESPACE_DNS, name="audio1"),
                user_id=uuid.uuid4(),
                name="sample-audio1.mp3",
                size=1024,
                duration=120,
                format="mp3",
                bitrate=128,
                standard_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
                dynamic_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/dynamic.wav",
                smooth_audio_url="https://is3.cloudhost.id/ahargunyllib-s3-testing/standard.wav",
            ),
            AudioProcessingResponse(
                id=uuid5(namespace=uuid.NAMESPACE_DNS, name="audio1"),
                user_id=uuid.uuid4(),
                name="sample-audio2.mp3",
                size=1024,
                duration=120,
                format="mp3",
                bitrate=128,
                standard_audio_url=None,
                dynamic_audio_url=None,
                smooth_audio_url=None,
            ),
        ]

        pagination = PaginationResponse(
            page=1,
            limit=10,
            total_data=2,
            total_page=1,
        )

        meta = GetAudioProcessingsMeta(pagination=pagination)

        return GetAudioProcessingsResponse(
            audio_processings=audio_processings,
            meta=meta,
        )
