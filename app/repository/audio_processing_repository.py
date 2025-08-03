from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.model.audio_processing_model import AudioProcessing


class AudioProcessingRepository:
    def __init__(
        self,
        engine: AsyncEngine,
        async_session_factory: async_sessionmaker[AsyncSession],
    ):
        self.engine = engine
        self.async_session = async_session_factory

    async def get_audio_processings_by_user_id(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> list[AudioProcessing]:
        query = text("""
            SELECT * FROM audio_processings
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        async with self.async_session() as session:
            result = await session.execute(
                query,
                {
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset,
                },
            )
            audio_processings = result.fetchall()

            return [
                AudioProcessing(
                    id=row.id,
                    user_id=row.user_id,
                    name=row.name,
                    size=row.size,
                    duration=row.duration,
                    format=row.format,
                    bitrate=row.bitrate,
                    standard_audio_url=row.standard_audio_url,
                    dynamic_audio_url=row.dynamic_audio_url,
                    smooth_audio_url=row.smooth_audio_url,
                    manual_audio_url=row.manual_audio_url,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                    user=None,  # User will be set later if needed
                )
                for row in audio_processings
            ]

    async def get_audio_processing_by_id(
        self, audio_processing_id: UUID
    ) -> AudioProcessing | None:
        query = text("""
            SELECT * FROM audio_processings WHERE id = :audio_processing_id
        """)

        async with self.async_session() as session:
            result = await session.execute(
                query, {"audio_processing_id": audio_processing_id}
            )
            audio_processing = result.fetchone()
            if audio_processing is None:
                return None

            return AudioProcessing(
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
                manual_audio_url=audio_processing.manual_audio_url,
                created_at=audio_processing.created_at,
                updated_at=audio_processing.updated_at,
            )

    async def count_audio_processings_by_user_id(self, user_id: UUID) -> int:
        query = text("""
            SELECT COUNT(*) FROM audio_processings WHERE user_id = :user_id
        """)

        async with self.async_session() as session:
            result = await session.execute(query, {"user_id": user_id})
            count = result.scalar_one_or_none()
            return count if count is not None else 0

    async def create_audio_processing(self, audio_processing: AudioProcessing) -> None:
        query = text("""
            INSERT INTO audio_processings (
                id, user_id, name, size, duration, format, bitrate, created_at, updated_at
            ) VALUES (
                :id, :user_id, :name, :size, :duration, :format, :bitrate, NOW(), NOW()
            )
        """)

        async with self.async_session() as session:
            await session.execute(
                query,
                {
                    "id": audio_processing.id,
                    "user_id": audio_processing.user_id,
                    "name": audio_processing.name,
                    "size": audio_processing.size,
                    "duration": audio_processing.duration,
                    "format": audio_processing.format,
                    "bitrate": audio_processing.bitrate,
                },
            )
            await session.commit()

            return

    async def update_audio_processing(self, audio_processing: AudioProcessing) -> None:
        query = text("""
            UPDATE audio_processings SET
                user_id = :user_id,
                name = :name,
                size = :size,
                duration = :duration,
                format = :format,
                bitrate = :bitrate,
                standard_audio_url = :standard_audio_url,
                dynamic_audio_url = :dynamic_audio_url,
                smooth_audio_url = :smooth_audio_url,
                manual_audio_url = :manual_audio_url,
                updated_at = NOW()
            WHERE id = :id
        """)

        async with self.async_session() as session:
            await session.execute(
                query,
                {
                    "id": audio_processing.id,
                    "user_id": audio_processing.user_id,
                    "name": audio_processing.name,
                    "size": audio_processing.size,
                    "duration": audio_processing.duration,
                    "format": audio_processing.format,
                    "bitrate": audio_processing.bitrate,
                    "standard_audio_url": audio_processing.standard_audio_url,
                    "dynamic_audio_url": audio_processing.dynamic_audio_url,
                    "smooth_audio_url": audio_processing.smooth_audio_url,
                    "manual_audio_url": audio_processing.manual_audio_url,
                },
            )
            await session.commit()

            return
