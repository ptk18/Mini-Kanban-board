from pydantic import BaseModel


class ColumnCount(BaseModel):
    column_id: int
    name: str
    position: int
    count: int


class DashboardOut(BaseModel):
    board_id: int
    total: int
    by_column: list[ColumnCount]
    overdue: int
    done: int
    progress_percent: float
