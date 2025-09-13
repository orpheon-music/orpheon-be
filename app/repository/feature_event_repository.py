from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db


class FeatureEventRepository:
    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    async def create_feature_event(
        self,
        feature_name: str,
        event_type: str,
        event_data: dict[str, str] | None = None,
    ) -> None:
        query = text("""
            INSERT INTO feature_events (feature_name, event_type, event_data, created_at)
            VALUES (:feature_name, :event_type, :event_data, now())
                     """)

        await self.db.execute(
            query,
            {
                "feature_name": feature_name,
                "event_type": event_type,
                "event_data": event_data,
            },
        )
        await self.db.commit()


def get_feature_event_repository(
    db: AsyncSession = Depends(get_db),
) -> FeatureEventRepository:
    return FeatureEventRepository(db)
