from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("board_id", "name", name="uq_labels_board_id_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)

    board: Mapped["Board"] = relationship(back_populates="labels")
    cards: Mapped[list["Card"]] = relationship(
        secondary="card_labels", back_populates="labels", passive_deletes=True
    )


class CardLabel(Base):
    __tablename__ = "card_labels"

    card_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )
