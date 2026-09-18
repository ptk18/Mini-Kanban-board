from typing import Literal

from pydantic import BaseModel

from app.schemas.card import Priority

Size = Literal["Small", "Medium", "Large"]


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
