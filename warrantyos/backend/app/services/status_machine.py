"""
Centralized Claim Status Machine — Part 1.2
No arbitrary transitions. All status changes go through `transition_claim`.
"""

from fastapi import HTTPException, status

# Valid states (spec 1.2)
VALID_STATUSES = {
    "SUBMITTED",
    "PROCESSING",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "MORE_INFORMATION_REQUIRED",
    "RESOLVED",
}

# Transition map: old -> set(new)
TRANSITIONS: dict[str, set[str]] = {
    "SUBMITTED": {"PROCESSING"},
    "PROCESSING": {"UNDER_REVIEW", "APPROVED", "REJECTED", "MORE_INFORMATION_REQUIRED"},
    "UNDER_REVIEW": {"APPROVED", "REJECTED", "MORE_INFORMATION_REQUIRED"},
    "APPROVED": {"RESOLVED"},
    "REJECTED": set(),  # terminal without manual reopen (not allowed in 1.2)
    "MORE_INFORMATION_REQUIRED": {"PROCESSING"},
    "RESOLVED": set(),  # terminal
}


def is_valid_transition(current: str, new: str) -> bool:
    if current not in VALID_STATUSES or new not in VALID_STATUSES:
        return False
    return new in TRANSITIONS.get(current, set())


def assert_valid_transition(current: str, new: str):
    if current == new:
        return
    if not is_valid_transition(current, new):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition: {current} -> {new}. Allowed: {sorted(TRANSITIONS.get(current, set())) or 'none (terminal)'}",
        )


def can_transition(current: str, new: str) -> bool:
    return is_valid_transition(current, new)
