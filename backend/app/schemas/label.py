from pydantic import BaseModel, ConfigDict, field_validator

NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 50


def _validate_name(value: str) -> str:
    value = value.strip()
    if not NAME_MIN_LENGTH <= len(value) <= NAME_MAX_LENGTH:
        raise ValueError(f"name must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters")
    return value


class LabelCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_name(value)


class LabelUpdate(LabelCreate):
    pass


class LabelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    name: str
