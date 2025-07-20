from typing import Annotated
from uuid import UUID

from fastapi import UploadFile
from fastapi.params import File
from pydantic import BaseModel

from app.dto.pagination_dto import PaginationResponse


class AudioProcessingResponse(BaseModel):
    id: UUID
    user_id: UUID

    name: str
    size: int
    duration: int
    format: str
    bitrate: int

    standard_audio_url: str | None
    dynamic_audio_url: str | None
    smooth_audio_url: str | None


class CreateAudioProcessingRequest(BaseModel):
    voice_file: Annotated[UploadFile, File()]
    instrument_file: Annotated[UploadFile, File()]
    reference_url: Annotated[str, File()]

    user_id: UUID


class CreateAudioProcessingResponse(BaseModel):
    audio_processing: AudioProcessingResponse


class GetAudioProcessingsQuery(BaseModel):
    page: int = 1


class GetAudioProcessingsMeta(BaseModel):
    pagination: PaginationResponse


class GetAudioProcessingsResponse(BaseModel):
    audio_processings: list[AudioProcessingResponse]
    meta: GetAudioProcessingsMeta
