from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_serializer


class UserOut(BaseModel):
    """Public view of a ``User`` row. Never carries ``password_hash``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> datetime:
        # Timestamps are stored as naive UTC (app.database.utcnow). Attaching the
        # offset makes the JSON carry an explicit "Z" so browsers do not read it as
        # local time. Every later *Out schema follows this convention.
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
