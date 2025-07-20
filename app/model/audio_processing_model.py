from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AudioProcessing(Base):
    __tablename__ = "audio_processings"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    format = Column(String(50), nullable=False)
    bitrate = Column(Integer, nullable=False)
    standard_audio_url = Column(String(255), nullable=True)
    dynamic_audio_url = Column(String(255), nullable=True)
    smooth_audio_url = Column(String(255), nullable=True)
    manual_audio_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default="now()", nullable=False)
    updated_at = Column(
        DateTime, server_default="now()", onupdate="now()", nullable=False
    )
