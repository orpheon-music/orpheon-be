from datetime import datetime
from uuid import UUID

from app.model.user_model import User


class AudioProcessing:
    id: UUID
    user_id: UUID
    name: str
    size: int
    duration: int
    format: str
    bitrate: int
    standard_audio_url: str | None = None
    dynamic_audio_url: str | None = None
    smooth_audio_url: str | None = None
    manual_audio_url: str | None = None
    created_at: datetime
    updated_at: datetime

    user: User | None

    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        name: str,
        size: int,
        duration: int,
        format: str,
        bitrate: int,
        created_at: datetime,
        updated_at: datetime,
        standard_audio_url: str | None = None,
        dynamic_audio_url: str | None = None,
        smooth_audio_url: str | None = None,
        manual_audio_url: str | None = None,
        user: User | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.size = size
        self.duration = duration
        self.format = format
        self.bitrate = bitrate
        self.standard_audio_url = standard_audio_url
        self.dynamic_audio_url = dynamic_audio_url
        self.smooth_audio_url = smooth_audio_url
        self.manual_audio_url = manual_audio_url
        self.created_at = created_at
        self.updated_at = updated_at
        self.user = user
