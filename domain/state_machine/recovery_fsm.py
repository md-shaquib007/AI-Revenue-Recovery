from datetime import datetime
from typing import Optional, Set, Tuple
from domain.models.enums import RecoveryState, ResolutionType


class RecoveryFSMError(Exception):
    pass


class InvalidStateTransitionError(RecoveryFSMError):
    def __init__(self, from_state: RecoveryState, to_state: RecoveryState):
        super().__init__(f"Invalid recovery state transition from {from_state} to {to_state}")


class RecoveryStateMachine:
    """
    Finite State Machine governing Recovery Case lifecycles.
    Ensures safe, deterministic state progression and guarantees that
    terminal states cannot be illegally re-opened.
    """

    ALLOWED_TRANSITIONS: Set[Tuple[RecoveryState, RecoveryState]] = {
        # From TRIAGING
        (RecoveryState.TRIAGING, RecoveryState.IN_GRACE_WINDOW),
        (RecoveryState.TRIAGING, RecoveryState.SCHEDULED_RETRY),
        (RecoveryState.TRIAGING, RecoveryState.LINK_SENT),
        (RecoveryState.TRIAGING, RecoveryState.ESCALATED_HUMAN),
        (RecoveryState.TRIAGING, RecoveryState.RECOVERED),
        (RecoveryState.TRIAGING, RecoveryState.CANCELLED),
        (RecoveryState.TRIAGING, RecoveryState.EXPIRED),

        # From IN_GRACE_WINDOW
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.SCHEDULED_RETRY),
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.LINK_SENT),
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.ESCALATED_HUMAN),
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.RECOVERED),
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.CANCELLED),
        (RecoveryState.IN_GRACE_WINDOW, RecoveryState.EXPIRED),

        # From SCHEDULED_RETRY
        (RecoveryState.SCHEDULED_RETRY, RecoveryState.RECOVERED),
        (RecoveryState.SCHEDULED_RETRY, RecoveryState.LINK_SENT),
        (RecoveryState.SCHEDULED_RETRY, RecoveryState.ESCALATED_HUMAN),
        (RecoveryState.SCHEDULED_RETRY, RecoveryState.CANCELLED),
        (RecoveryState.SCHEDULED_RETRY, RecoveryState.EXPIRED),

        # From LINK_SENT
        (RecoveryState.LINK_SENT, RecoveryState.RECOVERED),
        (RecoveryState.LINK_SENT, RecoveryState.PARTIALLY_RECOVERED),
        (RecoveryState.LINK_SENT, RecoveryState.SCHEDULED_RETRY),
        (RecoveryState.LINK_SENT, RecoveryState.LINK_SENT),
        (RecoveryState.LINK_SENT, RecoveryState.ESCALATED_HUMAN),
        (RecoveryState.LINK_SENT, RecoveryState.CANCELLED),
        (RecoveryState.LINK_SENT, RecoveryState.EXPIRED),

        # From ESCALATED_HUMAN
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.SCHEDULED_RETRY),
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.LINK_SENT),
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.PARTIALLY_RECOVERED),
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.RECOVERED),
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.CANCELLED),
        (RecoveryState.ESCALATED_HUMAN, RecoveryState.EXPIRED),

        # From PARTIALLY_RECOVERED
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.PARTIALLY_RECOVERED),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.RECOVERED),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.LINK_SENT),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.SCHEDULED_RETRY),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.ESCALATED_HUMAN),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.CANCELLED),
        (RecoveryState.PARTIALLY_RECOVERED, RecoveryState.EXPIRED),
    }

    TERMINAL_STATES = {
        RecoveryState.RECOVERED,
        RecoveryState.CANCELLED,
        RecoveryState.EXPIRED,
    }

    @classmethod
    def can_transition(cls, current_state: RecoveryState, target_state: RecoveryState) -> bool:
        if current_state == target_state:
            return True
        return (current_state, target_state) in cls.ALLOWED_TRANSITIONS

    @classmethod
    def validate_transition(cls, current_state: RecoveryState, target_state: RecoveryState):
        if not cls.can_transition(current_state, target_state):
            raise InvalidStateTransitionError(current_state, target_state)

    @classmethod
    def is_terminal(cls, state: RecoveryState) -> bool:
        return state in cls.TERMINAL_STATES
