"""Board-membership checks shared by every router that touches board data.

A user "belongs" to a board when they own it or have a ``BoardMember`` row.
Non-members get 404 rather than 403 so the API does not reveal which ids
exist (issue #5 allows either; 404 is the one every router should use).
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Board, BoardMember, Card, User
from app.services.auth import get_current_user


def is_board_member(db: Session, board_id: int, user_id: int) -> bool:
    board = db.get(Board, board_id)
    if board is None:
        return False
    if board.owner_id == user_id:
        return True
    membership = db.scalar(
        select(BoardMember.id).where(
            BoardMember.board_id == board_id, BoardMember.user_id == user_id
        )
    )
    return membership is not None


def _card_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")


def get_card_for_member(
    card_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Card:
    """The card at ``card_id`` if the caller belongs to its board, else 404."""
    card = db.get(Card, card_id)
    if card is None or not is_board_member(db, card.board_id, user.id):
        raise _card_not_found()
    return card
