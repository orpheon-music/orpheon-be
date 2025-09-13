from datetime import datetime


class FeatureEvent:
    id: int
    feature_name: str
    event_type: str
    event_data: dict[str, str] | None
    created_at: datetime

    def __init__(
        self,
        id: int,
        feature_name: str,
        event_type: str,
        created_at: datetime,
        event_data: dict[str, str] | None = None,
    ):
        self.id = id
        self.feature_name = feature_name
        self.event_type = event_type
        self.event_data = event_data
        self.created_at = created_at
