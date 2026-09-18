from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChecklistItem
from app.services.ordering import move, renumber

__all__ = ["move", "ordered_items", "renumber"]


def ordered_items(db: Session, card_id: int) -> list[ChecklistItem]:
    return list(
        db.scalars(
            select(ChecklistItem)
            .where(ChecklistItem.card_id == card_id)
            .order_by(ChecklistItem.position, ChecklistItem.id)
        )
    )
