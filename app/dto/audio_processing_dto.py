from typing import Annotated, Literal
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


class UpdateAudioProcessingQuery(BaseModel):
    audio_processing_id: UUID


class UpdateAudioProcessingRequest(BaseModel):
  manual_file: Annotated[UploadFile | None, File()] = None
  type: Literal["standard", "dynamic", "smooth"] | None = None


class GetAudioProcessingsQuery(BaseModel):
    page: int = 1


class GetAudioProcessingsMeta(BaseModel):
    pagination: PaginationResponse


class GetAudioProcessingsResponse(BaseModel):
    audio_processings: list[AudioProcessingResponse]
    meta: GetAudioProcessingsMeta

class GetAudioProcessingByIdQuery(BaseModel):
    audio_processing_id: UUID
class GetAudioProcessingByIdResponse(BaseModel):
    audio_processing: AudioProcessingResponse
