"""Cards (issue #7, absorbed #8).

Any board member may create, read, update, move and delete cards; non-members
get 404. References that point off the board (``column_id``, ``assignee_id``,
``parent_card_id``, ``label_ids``) are 422. Positions are 0-based and
contiguous per column; ``PATCH`` with ``column_id``/``position`` moves the
card and renumbers both columns. Deleting a card detaches its children
(``parent_card_id`` SET NULL) and cascades its checklist and comments.
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Board, Card, Column
from app.schemas.card import CardCreate, CardOut, CardUpdate
from app.services.access import get_board_for_member, get_card_for_member
from app.services.cards import (
    check_assignee,
    check_parent,
    column_on_board,
    labels_on_board,
    ordered_cards,
    place,
)
from app.services.ordering import renumber

router = APIRouter(tags=["cards"])


@router.get("/boards/{board_id}/cards", response_model=list[CardOut])
def list_cards(
    board: Board = Depends(get_board_for_member), db: Session = Depends(get_db)
) -> list[Card]:
    return list(
        db.scalars(
            select(Card)
            .join(Column, Card.column_id == Column.id)
            .where(Card.board_id == board.id)
            .options(selectinload(Card.labels), selectinload(Card.checklist_items))
            .order_by(Column.position, Card.position, Card.id)
        )
    )


@router.post(
    "/boards/{board_id}/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED
)
def create_card(
    body: CardCreate,
    board: Board = Depends(get_board_for_member),
    db: Session = Depends(get_db),
) -> Card:
    column = column_on_board(db, board, body.column_id)
    check_assignee(db, board, body.assignee_id)
    check_parent(db, board, None, body.parent_card_id)
    labels = labels_on_board(db, board, body.label_ids)
    card = Card(
        board_id=board.id,
        column_id=column.id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        due_date=body.due_date,
        assignee_id=body.assignee_id,
        parent_card_id=body.parent_card_id,
        position=0,
        labels=labels,
    )
    db.add(card)
    place(db, card, column.id, body.position)
    db.commit()
    db.refresh(card)
    return card


@router.get("/cards/{card_id}", response_model=CardOut)
def get_card(card: Card = Depends(get_card_for_member)) -> Card:
    return card


@router.patch("/cards/{card_id}", response_model=CardOut)
def update_card(
    body: CardUpdate,
    card: Card = Depends(get_card_for_member),
    db: Session = Depends(get_db),
) -> Card:
    board = card.board
    fields = body.model_fields_set
    if "column_id" in fields:
        column_on_board(db, board, body.column_id)
    if "assignee_id" in fields:
        check_assignee(db, board, body.assignee_id)
    if "parent_card_id" in fields:
        check_parent(db, board, card, body.parent_card_id)
    if "label_ids" in fields:
        card.labels = labels_on_board(db, board, body.label_ids)

    for name in ("title", "description", "priority", "due_date", "assignee_id", "parent_card_id"):
        if name in fields:
            setattr(card, name, getattr(body, name))

    if "column_id" in fields or "position" in fields:
        target_column = body.column_id if body.column_id is not None else card.column_id
        place(db, card, target_column, body.position)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card: Card = Depends(get_card_for_member), db: Session = Depends(get_db)
) -> Response:
    siblings = ordered_cards(db, card.column_id, exclude=card)
    db.delete(card)
    renumber(siblings)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
