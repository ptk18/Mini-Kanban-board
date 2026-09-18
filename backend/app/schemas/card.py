from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.checklist import ChecklistItemOut
from app.schemas.common import as_utc


class CardOut(BaseModel):
    """Card detail. ``checklist_items`` is ordered by ``position`` (see the
    relationship's ``order_by`` on the model)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    column_id: int
    parent_card_id: int | None
    title: str
    description: str
    priority: str
    due_date: datetime | None
    assignee_id: int | None
    position: int
    created_at: datetime
    updated_at: datetime
    checklist_items: list[ChecklistItemOut]

    @field_serializer("due_date", "created_at", "updated_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        return None if value is None else as_utc(value)
