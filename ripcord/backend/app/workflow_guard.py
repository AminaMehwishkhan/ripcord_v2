"""
workflow_guard.py

The single choke point between "we captured a value" and "we acted on it".
This is the architectural rule from the spec, made unavoidable in code:

    CRITICAL ENTITY -> RIPCORD VALIDATION -> VERIFIED? -> EXECUTE
                                           -> UNCERTAIN? -> CLARIFY -> VERIFY -> EXECUTE

No other module is allowed to call the simulated action layer directly.
"""
from __future__ import annotations

from .models import CriticalEntity, EntityStatus


class UnverifiedEntityError(Exception):
    """Raised if something tries to execute an action on an unverified entity."""


def execute_order_lookup(entity: CriticalEntity) -> str:
    """
    Simulated action layer. In the MVP this never touches a real system —
    see spec section 6 ("Safety rule") and section 3 ("MVP scope"). This is
    the ONLY function permitted to produce an "action" result, and it
    refuses to run unless the entity has been explicitly verified.
    """
    if entity.status != EntityStatus.VERIFIED:
        raise UnverifiedEntityError(
            f"Refusing to execute: entity status is {entity.status}, not VERIFIED."
        )
    if not entity.format_valid:
        # Belt and braces: even a "verified" value is refused if it cannot be an order number.
        raise UnverifiedEntityError(
            f"Refusing to execute: {entity.value!r} does not have the expected number of digits."
        )
    return f"Order {entity.value} located safely."


def can_execute(entity: CriticalEntity | None) -> bool:
    return entity is not None and entity.status == EntityStatus.VERIFIED and entity.format_valid
