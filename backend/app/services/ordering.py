"""Position bookkeeping shared by every ordered collection (columns on a
board, checklist items on a card, ...).

Positions are 0-based and contiguous within their parent. Every mutation
goes through ``renumber`` so a delete or a move never leaves a gap.
"""

from typing import Protocol


class Positioned(Protocol):
    position: int


def renumber(items: list) -> None:
    for index, item in enumerate(items):
        if item.position != index:
            item.position = index


def move(items: list, item: Positioned, position: int) -> None:
    """Move ``item`` to index ``position`` inside ``items`` and renumber.

    Callers validate ``0 <= position < len(items)`` first.
    """
    items.remove(item)
    items.insert(position, item)
    renumber(items)
