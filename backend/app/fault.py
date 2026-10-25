"""Demo-only fault injection (issue #45).

When the ``FAULT_INJECTION`` environment variable is set, ``/debug/fault``
is registered (see ``routers/debug.py``) and lets a developer make card
moves fail with ``500`` on purpose, so the error-rate alert and the on-call
responder can be exercised end to end. The production Blueprint never sets
the variable, so neither the route nor the failure path exists there.
"""

import os
from dataclasses import dataclass


def enabled_by_env() -> bool:
    return os.environ.get("FAULT_INJECTION", "") not in ("", "0", "false", "no")


@dataclass
class FaultState:
    card_move_fails: bool = False


STATE = FaultState()


class InjectedFault(RuntimeError):
    """Raised in the card-move path while the fault is switched on."""


def check_card_move() -> None:
    if STATE.card_move_fails:
        raise InjectedFault("fault injection: card moves are set to fail (POST /debug/fault)")
