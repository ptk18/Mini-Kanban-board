"""Position bookkeeping for a card's checklist.

Positions are 0-based and contiguous within a card. Every mutation goes
through ``renumber`` so a delete or a move never leaves a gap.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChecklistItem


def ordered_items(db: Session, card_id: int) -> list[ChecklistItem]:
    return list(
        db.scalars(
            select(ChecklistItem)
            .where(ChecklistItem.card_id == card_id)
            .order_by(ChecklistItem.position, ChecklistItem.id)
        )
    )


def renumber(items: list[ChecklistItem]) -> None:
    for index, item in enumerate(items):
        if item.position != index:
            item.position = index


def move(items: list[ChecklistItem], item: ChecklistItem, position: int) -> None:
    """Move ``item`` to index ``position`` inside ``items`` and renumber.

    Callers validate ``0 <= position < len(items)`` first.
    """
    items.remove(item)
    items.insert(position, item)
    renumber(items)
