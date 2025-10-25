import json
import logging
from typing import Literal
from uuid import UUID

import redis
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.config.redis import get_redis_client
from app.model.audio_processing_model import AudioProcessing

logger = logging.getLogger(__name__)


class AudioProcessingRepository:
    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
    ):
        self.db = db
        self.redis = redis_client

    async def get_audio_processings_by_user_id(
        self,
        user_id: UUID | None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[AudioProcessing]:
        # Check if the user has any audio processings in cache
        cache_key = f"user:{user_id}:audio_processings"
        cached_audio_processings = await self.redis.get(cache_key)
        if cached_audio_processings:
            logger.info(f"Cache hit for audio processings of user {user_id}")

            # Decode cached data
            cached_audio_processings = json.loads(cached_audio_processings)
            return [
                AudioProcessing(
                    id=UUID(item["id"]),
                    user_id=UUID(item["user_id"]),
                    name=item["name"],
                    size=item["size"],
                    duration=item["duration"],
                    format=item["format"],
                    bitrate=item["bitrate"],
                    standard_audio_url=item.get("standard_audio_url"),
                    dynamic_audio_url=item.get("dynamic_audio_url"),
                    smooth_audio_url=item.get("smooth_audio_url"),
                    manual_audio_url=item.get("manual_audio_url"),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                )
                for item in cached_audio_processings
            ]

        query = text("""
            SELECT * FROM audio_processings
            # WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await self.db.execute(
            query,
            {
                # "user_id": user_id,
                "user_id": "1 OR 1=1",  # Temporary bypass for user_id filtering
                "limit": limit,
                "offset": offset,
            },
        )

        audio_processings = result.fetchall()

        audio_processings = [
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

        # Cache the audio processings
        await self.redis.set(
            cache_key,
            json.dumps([ap.to_dict() for ap in audio_processings]),
            ex=3600,  # Cache for 1 hour
        )

        return audio_processings

    async def get_audio_processing_by_id(
        self, audio_processing_id: UUID
    ) -> AudioProcessing | None:
        # Check if the audio processing is in cache
        cache_key = f"audio_processing:{audio_processing_id}"
        cached_audio_processing = await self.redis.get(cache_key)
        if cached_audio_processing:
            logger.info(f"Cache hit for audio processing {audio_processing_id}")

            # Decode cached data
            cached_audio_processing = json.loads(cached_audio_processing)
            return AudioProcessing(
                id=UUID(cached_audio_processing["id"]),
                user_id=UUID(cached_audio_processing["user_id"]),
                name=cached_audio_processing["name"],
                size=cached_audio_processing["size"],
                duration=cached_audio_processing["duration"],
                format=cached_audio_processing["format"],
                bitrate=cached_audio_processing["bitrate"],
                standard_audio_url=cached_audio_processing.get("standard_audio_url"),
                dynamic_audio_url=cached_audio_processing.get("dynamic_audio_url"),
                smooth_audio_url=cached_audio_processing.get("smooth_audio_url"),
                manual_audio_url=cached_audio_processing.get("manual_audio_url"),
                created_at=cached_audio_processing["created_at"],
                updated_at=cached_audio_processing["updated_at"],
            )

        query = text("""
            SELECT * FROM audio_processings WHERE id = :audio_processing_id
        """)

        result = await self.db.execute(
            query, {"audio_processing_id": audio_processing_id}
        )
        audio_processing = result.fetchone()
        if audio_processing is None:
            return None

        audio_processing = AudioProcessing(
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

        # Cache the audio processing
        await self.redis.set(
            cache_key,
            json.dumps(audio_processing.to_dict()),
            ex=3600,  # Cache for 1 hour
        )

        return audio_processing

    async def count_audio_processings_by_user_id(self, user_id: UUID | None) -> int:
        query = text("""
            SELECT COUNT(*) FROM audio_processings WHERE user_id = :user_id
        """)

        result = await self.db.execute(query, {
            # "user_id": user_id
            "user_id": "1 OR 1=1"  # Temporary bypass for user_id filtering
        })
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

        await self.db.execute(
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
        await self.db.commit()

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

        await self.db.execute(
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
        await self.db.commit()

        # Update the cache after updating the audio processing
        cache_key = f"audio_processing:{audio_processing.id}"
        await self.redis.set(
            cache_key,
            json.dumps(audio_processing.to_dict()),
            ex=3600,  # Cache for 1 hour
        )

        # Clear the user audio processings cache
        user_cache_key = f"user:{audio_processing.user_id}:audio_processings"
        await self.redis.delete(user_cache_key)

        return

    async def get_audio_processing_stage(
        self, audio_processing_id: UUID
    ) -> Literal[0, 1, 2, 3, 4, 5] | None:
        cache_key = f"audio_processing:{audio_processing_id}:stage"
        cached_stage = await self.redis.get(cache_key)
        if cached_stage:
            logger.info(
                f"Cache hit for stage of audio processing {audio_processing_id}: {int(cached_stage)}"
            )
            return int(cached_stage)  # type: ignore

        logger.info(f"No cached stage for audio processing {audio_processing_id}")
        return None

    async def set_audio_processing_stage(
        self, audio_processing_id: UUID, stage: int
    ) -> None:
        logger.info(f"Setting stage {stage} for audio processing {audio_processing_id}")
        cache_key = f"audio_processing:{audio_processing_id}:stage"
        await self.redis.set(cache_key, stage)

    async def delete_audio_processing_stage(self, audio_processing_id: UUID) -> None:
        logger.info(f"Deleting stage for audio processing {audio_processing_id}")
        cache_key = f"audio_processing:{audio_processing_id}:stage"
        await self.redis.delete(cache_key)


def get_audio_processing_repository(
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis_client),
) -> AudioProcessingRepository:
    return AudioProcessingRepository(
        db=db,
        redis_client=redis,
    )
