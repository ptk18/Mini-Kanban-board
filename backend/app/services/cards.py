"""Card placement and reference checks shared by the card routes."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Board, Card, Column, Label
from app.services.access import is_board_member
from app.services.ordering import move, renumber


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def ordered_cards(db: Session, column_id: int, exclude: Card | None = None) -> list[Card]:
    cards = db.scalars(
        select(Card).where(Card.column_id == column_id).order_by(Card.position, Card.id)
    )
    return [card for card in cards if card is not exclude]


def column_on_board(db: Session, board: Board, column_id: int) -> Column:
    column = db.get(Column, column_id)
    if column is None or column.board_id != board.id:
        raise _unprocessable("column_id must be a column of this board")
    return column


def check_assignee(db: Session, board: Board, assignee_id: int | None) -> None:
    if assignee_id is not None and not is_board_member(db, board.id, assignee_id):
        raise _unprocessable("assignee_id must be a member of this board")


def check_parent(db: Session, board: Board, card: Card | None, parent_card_id: int | None) -> None:
    """``parent_card_id`` must be a card on the same board, and neither the
    card itself nor one of its descendants (that would make a cycle)."""
    if parent_card_id is None:
        return
    parent = db.get(Card, parent_card_id)
    if parent is None or parent.board_id != board.id:
        raise _unprocessable("parent_card_id must be a card on this board")
    if card is not None:
        ancestor: Card | None = parent
        while ancestor is not None:
            if ancestor.id == card.id:
                raise _unprocessable("parent_card_id cannot be the card itself or a descendant")
            ancestor = ancestor.parent


def labels_on_board(db: Session, board: Board, label_ids: list[int]) -> list[Label]:
    if not label_ids:
        return []
    labels = {
        label.id: label
        for label in db.scalars(
            select(Label).where(Label.board_id == board.id, Label.id.in_(label_ids))
        )
    }
    if len(labels) != len(label_ids):
        raise _unprocessable("label_ids must all be labels of this board")
    return [labels[label_id] for label_id in label_ids]


def place(db: Session, card: Card, column_id: int, position: int | None) -> None:
    """Put ``card`` into ``column_id`` at ``position`` (append when None),
    renumbering both the old and the new column."""
    if card.column_id != column_id:
        renumber(ordered_cards(db, card.column_id, exclude=card))
    siblings = ordered_cards(db, column_id, exclude=card)
    if position is None:
        position = len(siblings)
    if position > len(siblings):
        raise _unprocessable(f"position must be between 0 and {len(siblings)}")
    card.column_id = column_id
    siblings.insert(position, card)
    renumber(siblings)
