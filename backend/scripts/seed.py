"""Populate a demo board for local use and demos (issue #20).

    uv run python scripts/seed.py            # from backend/, JWT_SECRET not needed

Creates three users and one "Insurance Policy Automation" board owned by
the first, with five columns, labels, a dozen cards across every priority
(some overdue), assignees, checklists, comments and a parent/child pair.

Idempotent: the board is looked up by name and owner, and users by email;
a second run reports what is already there and inserts nothing. There is
no partial update — to reseed, delete the board (or the database file).
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

# Make ``app`` importable when run as ``python scripts/seed.py`` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402, F401
from app.database import SessionLocal, prepare_database, utcnow  # noqa: E402
from app.models import (  # noqa: E402
    Board,
    BoardMember,
    Card,
    ChecklistItem,
    Column,
    Comment,
    Label,
    User,
)
from app.services.auth import hash_password  # noqa: E402

BOARD_NAME = "Insurance Policy Automation"
COLUMN_NAMES = ("Backlog", "To Do", "In Progress", "Review", "Done")
LABEL_NAMES = ("bug", "feature", "compliance", "integration", "urgent")
DEMO_PASSWORD = "insurance-demo"
USERS = (
    ("ada@example.com", "Ada Lovelace"),
    ("grace@example.com", "Grace Hopper"),
    ("linus@example.com", "Linus Torvalds"),
)


def _days(n: int):
    return utcnow() + timedelta(days=n)


# (column, title, description, priority, due in days or None, assignee index or None,
#  labels, checklist items, comments as (author index, text))
CARDS = [
    ("Backlog", "Support multi-policy households", "Allow one customer record to hold several policies.",
     "low", None, None, ("feature",), (), ()),
    ("Backlog", "Archive lapsed policies after 24 months", "Nightly job; keep an audit trail.",
     "low", 30, 2, ("compliance",), ("Define retention rule", "Write the job", "Add audit entry"), ()),
    ("To Do", "Validate policy numbers on import", "Reject rows whose number fails the checksum.",
     "medium", 3, 1, ("bug",), ("Add checksum helper", "Reject invalid rows", "Report counts"),
     ((0, "Import from the legacy system starts next sprint, so this is needed first."),)),
    ("To Do", "Renewal reminder emails", "Send 30 and 7 days before expiry.",
     "medium", 10, None, ("feature",), ("30-day template", "7-day template"), ()),
    ("To Do", "Regulator quarterly export", "CSV in the format from the March circular.",
     "high", -2, 0, ("compliance", "urgent"), ("Match column order", "Include cancelled policies"),
     ((1, "Deadline was Monday — regulator already asked twice."), (0, "On it today."))),
    ("In Progress", "Automate premium recalculation", "Recalculate when the risk profile changes.",
     "high", 5, 0, ("feature",), ("Rule engine hook", "Recalculate on profile save", "Backfill existing"),
     ((2, "Backfill should run in batches of 500."),)),
    ("In Progress", "Claims webhook retries", "Retry failed webhook deliveries with backoff.",
     "medium", -5, 2, ("integration", "bug"), ("Exponential backoff", "Dead-letter after 5 tries"),
     ((0, "Overdue — blocked on the vendor's staging environment."),)),
    ("In Progress", "Broker portal SSO", "SAML login for partner brokers.",
     "high", 14, 1, ("integration",), (), ()),
    ("Review", "Fix rounding on pro-rata refunds", "Refunds were off by a cent on 31-day months.",
     "high", -1, 1, ("bug",), ("Unit test for 31-day month",), ((2, "Looks right, one nit in the test name."),)),
    ("Review", "Policy PDF template v2", "New layout from marketing.",
     "low", 7, 2, ("feature",), (), ()),
    ("Done", "Set up the CI pipeline", "Lint, tests and build on every push.",
     "medium", -10, 0, (), ("Lint", "Tests", "Build"), ()),
    ("Done", "Migrate customer table to new schema", "Split address into its own table.",
     "medium", -14, 1, ("compliance",), (), ((0, "Done and verified against the export."),)),
]
# (parent title, child title, description) — children go in the parent's column.
CHILDREN = [
    ("Automate premium recalculation", "Add risk-profile change event", "Emit an event when the profile is saved."),
    ("Automate premium recalculation", "Recalculation worker", "Consume the event and store the new premium."),
]


def seed(db: Session) -> dict[str, int]:
    """Seed ``db`` and return the number of rows created per table."""
    created = {"users": 0, "boards": 0, "columns": 0, "labels": 0, "cards": 0,
               "checklist_items": 0, "comments": 0, "board_members": 0}

    users: list[User] = []
    for email, display_name in USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password(DEMO_PASSWORD), display_name=display_name)
            db.add(user)
            created["users"] += 1
        users.append(user)
    db.flush()
    owner = users[0]

    if db.scalar(select(Board).where(Board.name == BOARD_NAME, Board.owner_id == owner.id)) is not None:
        db.commit()
        return created

    board = Board(name=BOARD_NAME, owner_id=owner.id)
    db.add(board)
    db.flush()
    created["boards"] += 1

    for index, user in enumerate(users):
        db.add(BoardMember(board_id=board.id, user_id=user.id, role="owner" if index == 0 else "member"))
        created["board_members"] += 1

    columns = {}
    for position, name in enumerate(COLUMN_NAMES):
        columns[name] = Column(board_id=board.id, name=name, position=position)
        db.add(columns[name])
        created["columns"] += 1

    labels = {}
    for name in LABEL_NAMES:
        labels[name] = Label(board_id=board.id, name=name)
        db.add(labels[name])
        created["labels"] += 1
    db.flush()

    positions = {name: 0 for name in COLUMN_NAMES}
    cards_by_title: dict[str, Card] = {}

    def add_card(column: str, title: str, description: str, priority: str, due, assignee, label_names) -> Card:
        card = Card(
            board_id=board.id,
            column_id=columns[column].id,
            title=title,
            description=description,
            priority=priority,
            due_date=_days(due) if due is not None else None,
            assignee_id=users[assignee].id if assignee is not None else None,
            position=positions[column],
            labels=[labels[name] for name in label_names],
        )
        positions[column] += 1
        db.add(card)
        created["cards"] += 1
        cards_by_title[title] = card
        return card

    for column, title, description, priority, due, assignee, label_names, checklist, comments in CARDS:
        card = add_card(column, title, description, priority, due, assignee, label_names)
        db.flush()
        for position, content in enumerate(checklist):
            db.add(ChecklistItem(card_id=card.id, content=content, completed=column == "Done", position=position))
            created["checklist_items"] += 1
        for author, text in comments:
            db.add(Comment(card_id=card.id, user_id=users[author].id, content=text))
            created["comments"] += 1

    for parent_title, title, description in CHILDREN:
        parent = cards_by_title[parent_title]
        column = next(name for name, col in columns.items() if col.id == parent.column_id)
        assignee = next((i for i, user in enumerate(users) if user.id == parent.assignee_id), None)
        child = add_card(column, title, description, parent.priority, None, assignee, ())
        child.parent_card_id = parent.id

    db.commit()
    return created


def main() -> None:
    prepare_database()
    with SessionLocal() as db:
        created = seed(db)
    if any(created.values()):
        print("Seeded:", ", ".join(f"{count} {table}" for table, count in created.items() if count))
        print(f"Log in with any of {', '.join(email for email, _ in USERS)} / password {DEMO_PASSWORD!r}")
    else:
        print(f"Nothing to do: {BOARD_NAME!r} and the demo users already exist.")


if __name__ == "__main__":
    main()
