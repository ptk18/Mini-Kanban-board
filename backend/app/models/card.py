from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow
from app.models.column import Column


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_cards_priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    column_id: Mapped[int] = mapped_column(Integer, ForeignKey("columns.id"), nullable=False)
    parent_card_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cards.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    board: Mapped["Board"] = relationship(back_populates="cards")
    column: Mapped[Column] = relationship(back_populates="cards")
    assignee: Mapped["User | None"] = relationship()
    parent: Mapped["Card | None"] = relationship(
        back_populates="children", remote_side=[id]
    )
    # SET NULL, not CASCADE: deleting a parent detaches its children.
    children: Mapped[list["Card"]] = relationship(
        back_populates="parent", passive_deletes=True
    )
    checklist_items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="card", cascade="all, delete-orphan", passive_deletes=True
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="card", cascade="all, delete-orphan", passive_deletes=True
    )
    labels: Mapped[list["Label"]] = relationship(
        secondary="card_labels", back_populates="cards", passive_deletes=True
    )
