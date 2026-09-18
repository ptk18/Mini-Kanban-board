from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Column


def ordered_columns(db: Session, board_id: int) -> list[Column]:
    return list(
        db.scalars(
            select(Column).where(Column.board_id == board_id).order_by(Column.position, Column.id)
        )
    )
