"""AI actions (issues #16 and #17).

Single-card actions — Improve, Prioritize, Estimate effort, Summarize,
Break down — build a prompt from the current card's own fields only
(title, description, priority, due date), ask the model for a JSON object,
and return it as a preview. **Preview routes write nothing** (plan §9.2).

How a preview becomes a change:

- Improve / Prioritize / Estimate: the client sends a normal
  ``PATCH /cards/{card_id}`` with the values the user approved.
- Break down: the client sends the user-edited task list to
  ``POST /ai/card/{card_id}/breakdown/apply``, the one AI route that
  writes — it creates the children with ``parent_card_id`` set, in the
  parent's column, and never calls the model.
- Natural-language creation (``POST /ai/create-task``): the proposal is
  shaped like a ``POST /boards/{board_id}/cards`` body without
  ``column_id``; once the user approves, the client posts it to that
  route with the column they chose. There is deliberately no
  ``create-task/apply``.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError

from app.models import Card
from sqlalchemy.orm import Session

from app.database import get_db, utcnow
from app.schemas.ai import (
    BreakdownApply,
    BreakdownOut,
    CreateTaskRequest,
    EstimateOut,
    ImproveOut,
    PrioritizeOut,
    ProposedCard,
    SummarizeOut,
)
from app.schemas.card import CardOut
from app.services.access import get_board_for_member, get_card_for_member
from app.services.auth import get_current_user
from app.services.ai import AIClient, AIError, get_ai_client, parse_json_reply
from app.services.cards import place

router = APIRouter(prefix="/ai", tags=["ai"])


def card_context(card: Card) -> str:
    due = card.due_date.isoformat(timespec="minutes") + " UTC" if card.due_date else "none"
    return (
        f"Title: {card.title}\n"
        f"Description: {card.description or '(empty)'}\n"
        f"Priority: {card.priority}\n"
        f"Due date: {due}"
    )


PREAMBLE = (
    "You are helping with one task card on a Kanban board. Use only the card "
    "below as context. Reply with a single JSON object and nothing else.\n\n"
)

PROMPTS = {
    "improve": (
        "Rewrite the card so the title is a short, specific action and the "
        "description states the goal, the concrete steps and what done looks "
        "like. Keep facts from the card; do not invent requirements.\n"
        'JSON shape: {"text": "<one or two sentences on what you changed and why>", '
        '"title": "<improved title>", "description": "<improved description>"}'
    ),
    "prioritize": (
        "Propose a priority for this card from exactly: low, medium, high. "
        "Consider urgency, the due date and the apparent effort.\n"
        'JSON shape: {"text": "<one or two sentences of reasoning>", '
        '"priority": "<low|medium|high>"}'
    ),
    "estimate": (
        "Estimate the effort of this card as a size from exactly: Small, Medium, "
        'Large, and a rough time such as "2 hours", "1 day" or "3 days".\n'
        'JSON shape: {"text": "<one or two sentences of reasoning>", '
        '"size": "<Small|Medium|Large>", "time_estimate": "<time>"}'
    ),
    "summarize": (
        "Summarize the card in at most three plain sentences for someone "
        "skimming the board.\n"
        'JSON shape: {"text": "<summary>"}'
    ),
    "breakdown": (
        "Break this card into 2 to 8 concrete child tasks that together "
        "complete it. Each child has a short action title and a one or two "
        "sentence description. Do not repeat the parent as a child.\n"
        'JSON shape: {"text": "<one sentence on how you split it>", '
        '"tasks": [{"title": "<title>", "description": "<description>"}, ...]}'
    ),
}

CREATE_TASK_PROMPT = (
    "You are helping create one task card on a Kanban board from the user's "
    "sentence. Reply with a single JSON object and nothing else.\n\n"
    "Extract a short, specific title and a description that keeps every "
    "detail the user gave (do not invent requirements). Propose a priority "
    "from exactly: low, medium, high (medium unless the text signals "
    "urgency). If the text names a deadline, resolve it to an ISO 8601 date "
    "or date-time in UTC relative to today ({today}); otherwise use null.\n"
    'JSON shape: {{"text": "<one sentence on what you understood>", '
    '"title": "<title>", "description": "<description>", '
    '"priority": "<low|medium|high>", "due_date": "<ISO 8601 or null>"}}\n\n'
    "User's request:\n{text}"
)


def build_prompt(action: str, card: Card) -> str:
    return f"{PREAMBLE}{PROMPTS[action]}\n\nCard:\n{card_context(card)}"


def _ask(prompt: str, ai: AIClient, schema: type[BaseModel]) -> Any:
    try:
        reply = ai.generate(prompt)
        data = parse_json_reply(reply)
    except AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI reply does not match the expected shape: {exc.error_count()} error(s)",
        ) from exc


def _run(action: str, card: Card, ai: AIClient, schema: type[BaseModel]) -> Any:
    return _ask(build_prompt(action, card), ai, schema)


@router.post("/card/{card_id}/improve", response_model=ImproveOut)
def improve(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("improve", card, ai, ImproveOut)


@router.post("/card/{card_id}/prioritize", response_model=PrioritizeOut)
def prioritize(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("prioritize", card, ai, PrioritizeOut)


@router.post("/card/{card_id}/estimate", response_model=EstimateOut)
def estimate(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("estimate", card, ai, EstimateOut)


@router.post("/card/{card_id}/summarize", response_model=SummarizeOut)
def summarize(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("summarize", card, ai, SummarizeOut)


@router.post("/card/{card_id}/breakdown", response_model=BreakdownOut)
def breakdown(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("breakdown", card, ai, BreakdownOut)


@router.post(
    "/card/{card_id}/breakdown/apply",
    response_model=list[CardOut],
    status_code=status.HTTP_201_CREATED,
)
def apply_breakdown(
    body: BreakdownApply,
    card: Card = Depends(get_card_for_member),
    db: Session = Depends(get_db),
) -> list[Card]:
    """Create the (user-edited) child tasks under ``card``: same board, same
    column, appended after the column's existing cards in the given order,
    ``parent_card_id`` = the card. Does not call the model."""
    children = []
    for task in body.tasks:
        child = Card(
            board_id=card.board_id,
            column_id=card.column_id,
            parent_card_id=card.id,
            title=task.title,
            description=task.description,
            position=0,
        )
        db.add(child)
        place(db, child, card.column_id, None)
        children.append(child)
    db.commit()
    for child in children:
        db.refresh(child)
    return children


@router.post("/create-task", response_model=ProposedCard)
def create_task(
    body: CreateTaskRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    ai: AIClient = Depends(get_ai_client),
) -> ProposedCard:
    """Turn free text into a proposed card for ``board_id``. Saves nothing;
    the client creates the card with ``POST /boards/{board_id}/cards``
    after approval (see the module docstring)."""
    get_board_for_member(body.board_id, user, db)
    prompt = CREATE_TASK_PROMPT.format(today=utcnow().date().isoformat(), text=body.text)
    return _ask(prompt, ai, ProposedCard)
