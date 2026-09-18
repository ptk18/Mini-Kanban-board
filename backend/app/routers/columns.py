"""Columns on a board (issue #5, absorbed #6).

Any board member can create, rename, reorder and delete columns; non-members
get 404. Positions are 0-based and contiguous per board.

Deleting a column that still holds cards is **refused with 409**. The
alternative (moving the cards to the first remaining column) silently
changes card state the user did not ask to change; refusing keeps the
decision with them, and the frontend confirm dialog (#27) can say so. The
database agrees: ``cards.column_id`` has no ON DELETE action, so a column
with cards cannot be deleted at that level either.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Board, Card, Column, User
from app.schemas.column import ColumnCreate, ColumnOut, ColumnUpdate
from app.services.access import get_board_for_member, is_board_member
from app.services.auth import get_current_user
from app.services.columns import ordered_columns
from app.services.ordering import move, renumber

router = APIRouter(tags=["columns"])


def get_column_for_member(
    column_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Column:
    column = db.get(Column, column_id)
    if column is None or not is_board_member(db, column.board_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return column


@router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnOut,
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    body: ColumnCreate,
    board: Board = Depends(get_board_for_member),
    db: Session = Depends(get_db),
) -> Column:
    column = Column(
        board_id=board.id, name=body.name, position=len(ordered_columns(db, board.id))
    )
    db.add(column)
    db.commit()
    db.refresh(column)
    return column


@router.patch("/columns/{column_id}", response_model=ColumnOut)
def update_column(
    body: ColumnUpdate,
    column: Column = Depends(get_column_for_member),
    db: Session = Depends(get_db),
) -> Column:
    if body.name is not None:
        column.name = body.name
    if body.position is not None:
        columns = ordered_columns(db, column.board_id)
        if body.position >= len(columns):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"position must be between 0 and {len(columns) - 1}",
            )
        move(columns, column, body.position)
    db.commit()
    db.refresh(column)
    return column


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column: Column = Depends(get_column_for_member), db: Session = Depends(get_db)
) -> Response:
    card_count = db.scalar(select(func.count()).select_from(Card).where(Card.column_id == column.id))
    if card_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Column still holds {card_count} card(s); move them first",
        )
    columns = ordered_columns(db, column.board_id)
    columns.remove(column)
    db.delete(column)
    renumber(columns)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
