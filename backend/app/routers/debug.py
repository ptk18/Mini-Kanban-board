"""``/debug/fault`` — switch the demo fault on and off.

Registered by ``main.py`` only when ``FAULT_INJECTION`` is set (never in
production). No authentication: it exists only on a developer's machine, on
the Compose network, to demonstrate alerting and the on-call responder.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app import fault

router = APIRouter(prefix="/debug", tags=["debug"])


class FaultBody(BaseModel):
    card_move_fails: bool


class FaultOut(BaseModel):
    card_move_fails: bool


@router.get("/fault", response_model=FaultOut)
def get_fault() -> fault.FaultState:
    return fault.STATE


@router.post("/fault", response_model=FaultOut)
def set_fault(body: FaultBody) -> fault.FaultState:
    fault.STATE.card_move_fails = body.card_move_fails
    return fault.STATE
