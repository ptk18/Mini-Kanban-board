"""Plain-text comments on cards (issue #10).

Any board member can post and read. Editing and deleting is limited to the
comment's author: another member gets 403 (they can see the comment, they
just may not change it), a non-member gets 404 like everywhere else.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Card, Comment, User
from app.schemas.comment import CommentCreate, CommentOut, CommentUpdate
from app.services.access import get_card_for_member, is_board_member
from app.services.auth import get_current_user

router = APIRouter(tags=["comments"])


def _comment_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")


def get_own_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Comment:
    comment = db.get(Comment, comment_id)
    if comment is None or not is_board_member(db, comment.card.board_id, user.id):
        raise _comment_not_found()
    if comment.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can change this comment",
        )
    return comment


@router.get("/cards/{card_id}/comments", response_model=list[CommentOut])
def list_comments(
    card: Card = Depends(get_card_for_member), db: Session = Depends(get_db)
) -> list[Comment]:
    return list(
        db.scalars(
            select(Comment)
            .where(Comment.card_id == card.id)
            .options(selectinload(Comment.user))
            .order_by(Comment.created_at, Comment.id)
        )
    )


@router.post(
    "/cards/{card_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    body: CommentCreate,
    card: Card = Depends(get_card_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Comment:
    comment = Comment(card_id=card.id, user_id=user.id, content=body.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    body: CommentUpdate,
    comment: Comment = Depends(get_own_comment),
    db: Session = Depends(get_db),
) -> Comment:
    comment.content = body.content
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment: Comment = Depends(get_own_comment), db: Session = Depends(get_db)
) -> Response:
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
