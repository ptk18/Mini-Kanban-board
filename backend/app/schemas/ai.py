from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.schemas.card import Priority, _to_naive_utc, _validate_description, _validate_title
from app.schemas.common import as_utc

Size = Literal["Small", "Medium", "Large"]
BREAKDOWN_MAX_TASKS = 20
CREATE_TASK_MAX_CHARS = 2000


class ImproveOut(BaseModel):
    """A rewritten title and description the user may apply via card PATCH."""

    text: str
    title: str
    description: str


class PrioritizeOut(BaseModel):
    text: str
    priority: Priority


class EstimateOut(BaseModel):
    text: str
    size: Size
    time_estimate: str


class SummarizeOut(BaseModel):
    text: str


class ProposedTask(BaseModel):
    """One child task as proposed by the model or edited by the user."""

    title: str
    description: str = ""

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _validate_title(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _validate_description(value)


class BreakdownOut(BaseModel):
    text: str
    tasks: list[ProposedTask] = Field(min_length=1, max_length=BREAKDOWN_MAX_TASKS)


class BreakdownApply(BaseModel):
    tasks: list[ProposedTask] = Field(min_length=1, max_length=BREAKDOWN_MAX_TASKS)


class CreateTaskRequest(BaseModel):
    board_id: int
    text: str

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= CREATE_TASK_MAX_CHARS:
            raise ValueError(f"text must be 1-{CREATE_TASK_MAX_CHARS} characters")
        return value


class ProposedCard(BaseModel):
    """Shaped like a ``POST /boards/{board_id}/cards`` body minus
    ``column_id`` so the approved proposal can be posted as-is."""

    text: str
    title: str
    description: str = ""
    priority: Priority = "medium"
    due_date: datetime | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _validate_title(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _validate_description(value)

    @field_validator("due_date")
    @classmethod
    def _due_date(cls, value: datetime | None) -> datetime | None:
        return _to_naive_utc(value)

    @field_serializer("due_date")
    def _serialize_due_date(self, value: datetime | None) -> datetime | None:
        return None if value is None else as_utc(value)
