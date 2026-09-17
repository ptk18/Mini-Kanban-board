from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship()
    # Children on CASCADE foreign keys: passive_deletes lets SQLite do the
    # cascade in one statement; delete-orphan keeps ORM deletes consistent
    # with it when the collections are already loaded.
    members: Mapped[list["BoardMember"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )
    columns: Mapped[list["Column"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )
    cards: Mapped[list["Card"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )
    labels: Mapped[list["Label"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="board", cascade="all, delete-orphan", passive_deletes=True
    )


class BoardMember(Base):
    __tablename__ = "board_members"
    __table_args__ = (
        UniqueConstraint("board_id", "user_id", name="uq_board_members_board_id_user_id"),
        CheckConstraint("role IN ('owner', 'member')", name="ck_board_members_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    board: Mapped["Board"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()
