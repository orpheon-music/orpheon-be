from typing import Annotated, Literal
from uuid import UUID

from fastapi import Form, UploadFile
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

    stage: Literal[0, 1, 2, 3, 4, 5]

    created_at: str
    updated_at: str


class CreateAudioProcessingRequest(BaseModel):
    voice_file: Annotated[UploadFile, File()]
    instrument_file: Annotated[UploadFile | None, File()] = None
    reference_file: Annotated[UploadFile, File()]
    is_denoise: Annotated[bool, Form()]
    is_autotune: Annotated[bool, Form()]

    user_id: UUID


class CreateAudioProcessingResponse(BaseModel):
    audio_processing: AudioProcessingResponse


class UpdateAudioProcessingQuery(BaseModel):
    audio_processing_id: UUID


class UpdateAudioProcessingRequest(BaseModel):
    manual_file: Annotated[UploadFile | None, File()] = None
    type: Literal["standard", "dynamic", "smooth"] | None = None

class UpdateAudioProcessingResultParams(BaseModel):
    audio_processing_id: UUID

class UpdateAudioProcessingResultRequest(BaseModel):
    standard_file: Annotated[str, Form()]
    dynamic_file: Annotated[str, Form()]
    smooth_file: Annotated[str, Form()]

class UpdateAudioProcessingStageParams(BaseModel):
    audio_processing_id: UUID

class UpdateAudioProcessingStageRequest(BaseModel):
    stage: Literal[0, 1, 2, 3, 4, 5]

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
