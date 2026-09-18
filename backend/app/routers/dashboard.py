"""Board dashboard (issue #13): the four simple metrics, nothing else.

**How "Done" is identified:** a column counts as Done when its name,
trimmed and lower-cased, equals ``done`` — so the default "Done" column
qualifies, as does a renamed "done " or "DONE". Every such column counts.
Board members can rename columns freely, and there is no per-column flag
in the schema (plan §13), so name matching is the only signal available;
it is documented in the README so users know the rule.

- ``total``: every card on the board.
- ``by_column``: one entry per column in position order, zero included.
- ``overdue``: cards with ``due_date < now`` (naive UTC, ``utcnow()``)
  that are not in a Done column.
- ``progress_percent``: ``done / total * 100`` rounded to one decimal,
  ``0`` when the board has no cards.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.models import Board, Card, Column
from app.schemas.dashboard import ColumnCount, DashboardOut
from app.services.access import get_board_for_member

router = APIRouter(tags=["dashboard"])

DONE_COLUMN_NAME = "done"


def is_done_column(column: Column) -> bool:
    return column.name.strip().lower() == DONE_COLUMN_NAME


@router.get("/boards/{board_id}/dashboard", response_model=DashboardOut)
def get_dashboard(
    board: Board = Depends(get_board_for_member), db: Session = Depends(get_db)
) -> DashboardOut:
    columns = list(
        db.scalars(
            select(Column).where(Column.board_id == board.id).order_by(Column.position, Column.id)
        )
    )
    counts = dict(
        db.execute(
            select(Card.column_id, func.count())
            .where(Card.board_id == board.id)
            .group_by(Card.column_id)
        ).all()
    )
    done_ids = [column.id for column in columns if is_done_column(column)]

    by_column = [
        ColumnCount(
            column_id=column.id,
            name=column.name,
            position=column.position,
            count=counts.get(column.id, 0),
        )
        for column in columns
    ]
    total = sum(entry.count for entry in by_column)
    done = sum(counts.get(column_id, 0) for column_id in done_ids)

    overdue_query = select(func.count()).select_from(Card).where(
        Card.board_id == board.id, Card.due_date < utcnow()
    )
    if done_ids:
        overdue_query = overdue_query.where(Card.column_id.not_in(done_ids))
    overdue = db.scalar(overdue_query) or 0

    return DashboardOut(
        board_id=board.id,
        total=total,
        by_column=by_column,
        overdue=overdue,
        done=done,
        progress_percent=round(done / total * 100, 1) if total else 0.0,
    )
