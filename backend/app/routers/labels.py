"""Labels per board (issue #7, absorbed #8). Any member may manage them.
Names are unique per board (409 on a duplicate). Deleting a label removes
it from every card through the ``card_labels`` ON DELETE CASCADE."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Board, Label, User
from app.schemas.label import LabelCreate, LabelOut, LabelUpdate
from app.services.access import get_board_for_member, is_board_member
from app.services.auth import get_current_user

router = APIRouter(tags=["labels"])


def _name_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail="A label with this name already exists"
    )


def get_label_for_member(
    label_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Label:
    label = db.get(Label, label_id)
    if label is None or not is_board_member(db, label.board_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    return label


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _name_conflict() from None


@router.get("/boards/{board_id}/labels", response_model=list[LabelOut])
def list_labels(
    board: Board = Depends(get_board_for_member), db: Session = Depends(get_db)
) -> list[Label]:
    return list(db.scalars(select(Label).where(Label.board_id == board.id).order_by(Label.id)))


@router.post(
    "/boards/{board_id}/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED
)
def create_label(
    body: LabelCreate,
    board: Board = Depends(get_board_for_member),
    db: Session = Depends(get_db),
) -> Label:
    label = Label(board_id=board.id, name=body.name)
    db.add(label)
    _commit_or_conflict(db)
    db.refresh(label)
    return label


@router.patch("/labels/{label_id}", response_model=LabelOut)
def rename_label(
    body: LabelUpdate,
    label: Label = Depends(get_label_for_member),
    db: Session = Depends(get_db),
) -> Label:
    label.name = body.name
    _commit_or_conflict(db)
    db.refresh(label)
    return label


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(
    label: Label = Depends(get_label_for_member), db: Session = Depends(get_db)
) -> Response:
    db.delete(label)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
