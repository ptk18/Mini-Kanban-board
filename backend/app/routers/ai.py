"""Single-card AI actions (issue #16): Improve, Prioritize, Estimate effort,
Summarize.

Each action builds a prompt from the current card's own fields only (title,
description, priority, due date), asks the model for a JSON object, and
returns it as a preview. **Nothing is written to the database** — applying
a suggestion is a normal ``PATCH /cards/{card_id}`` the user sends after
approving (plan §9.2). Break down and natural-language creation are #17
and #18.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError

from app.models import Card
from app.schemas.ai import EstimateOut, ImproveOut, PrioritizeOut, SummarizeOut
from app.services.access import get_card_for_member
from app.services.ai import AIClient, AIError, get_ai_client, parse_json_reply

router = APIRouter(prefix="/ai/card", tags=["ai"])


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
}


def build_prompt(action: str, card: Card) -> str:
    return f"{PREAMBLE}{PROMPTS[action]}\n\nCard:\n{card_context(card)}"


def _run(action: str, card: Card, ai: AIClient, schema: type[BaseModel]) -> Any:
    try:
        reply = ai.generate(build_prompt(action, card))
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


@router.post("/{card_id}/improve", response_model=ImproveOut)
def improve(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("improve", card, ai, ImproveOut)


@router.post("/{card_id}/prioritize", response_model=PrioritizeOut)
def prioritize(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("prioritize", card, ai, PrioritizeOut)


@router.post("/{card_id}/estimate", response_model=EstimateOut)
def estimate(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("estimate", card, ai, EstimateOut)


@router.post("/{card_id}/summarize", response_model=SummarizeOut)
def summarize(card: Card = Depends(get_card_for_member), ai: AIClient = Depends(get_ai_client)):
    return _run("summarize", card, ai, SummarizeOut)
