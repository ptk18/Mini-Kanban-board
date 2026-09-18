from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas.checklist import ChecklistItemOut
from app.schemas.common import as_utc
from app.schemas.label import LabelOut

Priority = Literal["low", "medium", "high"]

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 5000


def _validate_title(value: str) -> str:
    value = value.strip()
    if not TITLE_MIN_LENGTH <= len(value) <= TITLE_MAX_LENGTH:
        raise ValueError(f"title must be {TITLE_MIN_LENGTH}-{TITLE_MAX_LENGTH} characters")
    return value


def _validate_description(value: str) -> str:
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(f"description must be at most {DESCRIPTION_MAX_LENGTH} characters")
    return value


def _to_naive_utc(value: datetime | None) -> datetime | None:
    # Stored timestamps are naive UTC (app.database.utcnow). An aware input is
    # converted; a naive input is taken as UTC already.
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _unique_ids(value: list[int]) -> list[int]:
    return list(dict.fromkeys(value))


class _CardFieldValidators(BaseModel):
    """Validators shared by ``CardCreate`` and ``CardUpdate``; the fields
    themselves live on the subclasses (hence ``check_fields=False``)."""

    @field_validator("title", check_fields=False)
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _validate_title(value)

    @field_validator("description", check_fields=False)
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return None if value is None else _validate_description(value)

    @field_validator("due_date", check_fields=False)
    @classmethod
    def _due_date(cls, value: datetime | None) -> datetime | None:
        return _to_naive_utc(value)

    @field_validator("label_ids", check_fields=False)
    @classmethod
    def _label_ids(cls, value: list[int] | None) -> list[int] | None:
        return None if value is None else _unique_ids(value)


class CardCreate(_CardFieldValidators):
    title: str
    description: str = ""
    column_id: int
    priority: Priority = "medium"
    due_date: datetime | None = None
    assignee_id: int | None = None
    parent_card_id: int | None = None
    label_ids: list[int] = Field(default_factory=list)
    # None appends at the end of the column.
    position: int | None = Field(default=None, ge=0)



class CardUpdate(_CardFieldValidators):
    """Partial update. ``column_id`` and/or ``position`` move the card:
    a new column without a position appends there; a position alone
    reorders within the current column. ``label_ids`` replaces the whole
    set. Explicit ``null`` clears ``due_date``, ``assignee_id`` and
    ``parent_card_id``."""

    title: str | None = None
    description: str | None = None
    column_id: int | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    assignee_id: int | None = None
    parent_card_id: int | None = None
    label_ids: list[int] | None = None
    position: int | None = Field(default=None, ge=0)


    _NOT_NULLABLE = ("title", "description", "column_id", "priority", "label_ids", "position")

    @model_validator(mode="after")
    def _check_fields(self) -> "CardUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for name in self._NOT_NULLABLE:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class CardOut(BaseModel):
    """Card detail. ``checklist_items`` is ordered by ``position`` (see the
    relationship's ``order_by`` on the model); ``labels`` by id."""

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
    labels: list[LabelOut]
    checklist_items: list[ChecklistItemOut]

    @field_serializer("due_date", "created_at", "updated_at")
    def _serialize_utc(self, value: datetime | None) -> datetime | None:
        return None if value is None else as_utc(value)
