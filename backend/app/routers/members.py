"""Board membership (issue #11): permanent invite link, join, invite by
email, list and remove members.

- ``POST /boards/{board_id}/invite`` (owner) returns the board's invite
  token, generating it on first use; it never changes afterwards.
- ``POST /invite/{token}/join`` adds the caller as ``member``. Joining a
  board they already belong to is a no-op that still returns 200
  (``joined: false``); the ``board_members`` unique constraint backs this.
- ``POST /boards/{board_id}/members`` (owner) adds an existing user by
  email, also idempotent.
- ``DELETE /boards/{board_id}/members/{user_id}`` (owner) removes a member;
  the owner cannot be removed (409). Cards on the board assigned to the
  removed user are unassigned, since ``assignee_id`` must be a member.

Non-members get 404 on board-scoped routes; a member on an owner-only route
gets 403.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Board, BoardMember, Card, User
from app.schemas.board import BoardOut
from app.schemas.member import InviteByEmail, InviteOut, JoinOut, MemberOut
from app.services.access import get_board_for_member, get_board_for_owner, role_on
from app.services.auth import get_current_user

router = APIRouter(tags=["members"])

INVITE_PATH = "/invite/{token}"


def _member_out(membership: BoardMember) -> MemberOut:
    return MemberOut(
        user_id=membership.user_id,
        user_email=membership.user.email,
        user_display_name=membership.user.display_name,
        role=membership.role,
        created_at=membership.created_at,
    )


def _ensure_member(db: Session, board: Board, user: User) -> tuple[BoardMember, bool]:
    """Return the user's membership row, creating it if missing.

    The second value says whether it was created. A concurrent insert of
    the same row loses to the unique constraint and is treated as "already
    a member", so a double-submit never turns into a 500.
    """
    existing = db.scalar(
        select(BoardMember).where(
            BoardMember.board_id == board.id, BoardMember.user_id == user.id
        )
    )
    if existing is not None:
        return existing, False
    membership = BoardMember(board_id=board.id, user_id=user.id, role=role_on(board, user.id))
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _ensure_member(db, board, user)[0], False
    db.refresh(membership)
    return membership, True


@router.post("/boards/{board_id}/invite", response_model=InviteOut)
def get_or_create_invite(
    board: Board = Depends(get_board_for_owner), db: Session = Depends(get_db)
) -> InviteOut:
    if board.invite_token is None:
        board.invite_token = secrets.token_urlsafe(32)
        db.commit()
        db.refresh(board)
    return InviteOut(
        board_id=board.id,
        invite_token=board.invite_token,
        invite_path=INVITE_PATH.format(token=board.invite_token),
    )


@router.post("/invite/{token}/join", response_model=JoinOut)
def join_by_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JoinOut:
    board = db.scalar(select(Board).where(Board.invite_token == token))
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")
    _, joined = _ensure_member(db, board, user)
    return JoinOut(
        board=BoardOut(
            id=board.id,
            name=board.name,
            owner_id=board.owner_id,
            role=role_on(board, user.id),
            created_at=board.created_at,
            updated_at=board.updated_at,
        ),
        joined=joined,
    )


@router.get("/boards/{board_id}/members", response_model=list[MemberOut])
def list_members(
    board: Board = Depends(get_board_for_member), db: Session = Depends(get_db)
) -> list[MemberOut]:
    # Owner first, then in joining order.
    rows = db.scalars(
        select(BoardMember)
        .where(BoardMember.board_id == board.id)
        .order_by((BoardMember.role != "owner"), BoardMember.created_at, BoardMember.id)
    )
    return [_member_out(row) for row in rows]


@router.post("/boards/{board_id}/members", response_model=MemberOut)
def invite_by_email(
    body: InviteByEmail,
    response: Response,
    board: Board = Depends(get_board_for_owner),
    db: Session = Depends(get_db),
) -> MemberOut:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with this email"
        )
    membership, created = _ensure_member(db, board, user)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _member_out(membership)


@router.delete("/boards/{board_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    board: Board = Depends(get_board_for_owner),
    db: Session = Depends(get_db),
) -> Response:
    if user_id == board.owner_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="The owner cannot be removed"
        )
    membership = db.scalar(
        select(BoardMember).where(
            BoardMember.board_id == board.id, BoardMember.user_id == user_id
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    db.delete(membership)
    db.execute(
        update(Card)
        .where(Card.board_id == board.id, Card.assignee_id == user_id)
        .values(assignee_id=None)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
