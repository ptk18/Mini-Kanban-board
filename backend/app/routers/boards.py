"""Boards (issue #5).

Visibility: a board is visible to its owner and to users with a
``board_members`` row. Non-members get 404 on every board route so ids are
not enumerable; a member who is not the owner gets 403 on owner-only
actions (delete).

Creating a board also creates the owner's ``board_members`` row and the
three default columns "To Do", "In Progress", "Done".
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Board, BoardMember, Column, User
from app.schemas.board import BoardCreate, BoardDetailOut, BoardOut, BoardUpdate
from app.schemas.column import ColumnOut
from app.services.access import get_board_for_member, get_board_for_owner, role_on
from app.services.auth import get_current_user
from app.services.columns import ordered_columns

router = APIRouter(prefix="/boards", tags=["boards"])

DEFAULT_COLUMN_NAMES = ("To Do", "In Progress", "Done")


def _board_out(board: Board, user: User) -> BoardOut:
    return BoardOut(
        id=board.id,
        name=board.name,
        owner_id=board.owner_id,
        role=role_on(board, user.id),
        created_at=board.created_at,
        updated_at=board.updated_at,
    )


def _board_detail(board: Board, user: User, db: Session) -> BoardDetailOut:
    return BoardDetailOut(
        **_board_out(board, user).model_dump(),
        columns=[ColumnOut.model_validate(c) for c in ordered_columns(db, board.id)],
    )


@router.get("", response_model=list[BoardOut])
def list_boards(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BoardOut]:
    member_of = select(BoardMember.board_id).where(BoardMember.user_id == user.id)
    boards = db.scalars(
        select(Board)
        .where(or_(Board.owner_id == user.id, Board.id.in_(member_of)))
        .order_by(Board.created_at, Board.id)
    )
    return [_board_out(board, user) for board in boards]


@router.post("", response_model=BoardDetailOut, status_code=status.HTTP_201_CREATED)
def create_board(
    body: BoardCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardDetailOut:
    board = Board(name=body.name, owner_id=user.id)
    db.add(board)
    db.flush()
    db.add(BoardMember(board_id=board.id, user_id=user.id, role="owner"))
    db.add_all(
        Column(board_id=board.id, name=name, position=position)
        for position, name in enumerate(DEFAULT_COLUMN_NAMES)
    )
    db.commit()
    db.refresh(board)
    return _board_detail(board, user, db)


@router.get("/{board_id}", response_model=BoardDetailOut)
def get_board(
    board: Board = Depends(get_board_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardDetailOut:
    return _board_detail(board, user, db)


@router.patch("/{board_id}", response_model=BoardOut)
def rename_board(
    body: BoardUpdate,
    board: Board = Depends(get_board_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BoardOut:
    board.name = body.name
    db.commit()
    db.refresh(board)
    return _board_out(board, user)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board: Board = Depends(get_board_for_owner), db: Session = Depends(get_db)
) -> Response:
    # Members, columns, cards, labels and their children go with it via the
    # ON DELETE CASCADE foreign keys (see app/models/board.py).
    db.delete(board)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
