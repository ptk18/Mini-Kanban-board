from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTENT_MIN_LENGTH = 1
CONTENT_MAX_LENGTH = 500


def _validate_content(value: str) -> str:
    value = value.strip()
    if not CONTENT_MIN_LENGTH <= len(value) <= CONTENT_MAX_LENGTH:
        raise ValueError(
            f"content must be {CONTENT_MIN_LENGTH}-{CONTENT_MAX_LENGTH} characters"
        )
    return value


class ChecklistItemCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return _validate_content(value)


class ChecklistItemUpdate(BaseModel):
    """Partial update: every field is optional, at least one must be present.

    ``position`` is the target index in the card's list (0-based, contiguous);
    the upper bound depends on the list length so the router checks it.
    """

    content: str | None = None
    completed: bool | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("content")
    @classmethod
    def _content(cls, value: str | None) -> str | None:
        return None if value is None else _validate_content(value)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ChecklistItemUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one of content, completed, position is required")
        return self


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    content: str
    completed: bool
    position: int
