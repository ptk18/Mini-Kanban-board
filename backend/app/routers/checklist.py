"""Flat checklists on cards (issue #9). No nesting.

Item routes live under ``/checklist/{item_id}`` rather than under the card
because the item id alone identifies the card; membership is still checked
against the card's board on every request.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, ChecklistItem, User
from app.schemas.checklist import ChecklistItemCreate, ChecklistItemOut, ChecklistItemUpdate
from app.services.access import get_card_for_member, is_board_member
from app.services.auth import get_current_user
from app.services.checklist import move, ordered_items, renumber

router = APIRouter(tags=["checklist"])


def _item_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Checklist item not found"
    )


def get_item_for_member(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChecklistItem:
    item = db.get(ChecklistItem, item_id)
    if item is None or not is_board_member(db, item.card.board_id, user.id):
        raise _item_not_found()
    return item


@router.get("/cards/{card_id}/checklist", response_model=list[ChecklistItemOut])
def list_items(
    card: Card = Depends(get_card_for_member), db: Session = Depends(get_db)
) -> list[ChecklistItem]:
    return ordered_items(db, card.id)


@router.post(
    "/cards/{card_id}/checklist",
    response_model=ChecklistItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_item(
    body: ChecklistItemCreate,
    card: Card = Depends(get_card_for_member),
    db: Session = Depends(get_db),
) -> ChecklistItem:
    # New items go to the end; ordered_items has the current length.
    item = ChecklistItem(
        card_id=card.id, content=body.content, position=len(ordered_items(db, card.id))
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/checklist/{item_id}", response_model=ChecklistItemOut)
def update_item(
    body: ChecklistItemUpdate,
    item: ChecklistItem = Depends(get_item_for_member),
    db: Session = Depends(get_db),
) -> ChecklistItem:
    if body.content is not None:
        item.content = body.content
    if body.completed is not None:
        item.completed = body.completed
    if body.position is not None:
        items = ordered_items(db, item.card_id)
        if body.position >= len(items):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"position must be between 0 and {len(items) - 1}",
            )
        move(items, item, body.position)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/checklist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item: ChecklistItem = Depends(get_item_for_member), db: Session = Depends(get_db)
) -> Response:
    items = ordered_items(db, item.card_id)
    items.remove(item)
    db.delete(item)
    renumber(items)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
