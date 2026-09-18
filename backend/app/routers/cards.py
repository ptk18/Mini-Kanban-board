"""Card detail (the read half of issue #7, needed by #9 for checklists)."""

from fastapi import APIRouter, Depends

from app.models import Card
from app.schemas.card import CardOut
from app.services.access import get_card_for_member

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/{card_id}", response_model=CardOut)
def get_card(card: Card = Depends(get_card_for_member)) -> Card:
    return card
