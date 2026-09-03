import pytest
from domain.models.enums import RecoveryState
from domain.state_machine.recovery_fsm import InvalidStateTransitionError, RecoveryStateMachine


def test_valid_transitions_from_triaging():
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.IN_GRACE_WINDOW)
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.SCHEDULED_RETRY)
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.LINK_SENT)
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.ESCALATED_HUMAN)
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.RECOVERED)
    assert RecoveryStateMachine.can_transition(RecoveryState.TRIAGING, RecoveryState.CANCELLED)


def test_invalid_transitions_from_terminal_states():
    # Terminal states (RECOVERED, CANCELLED, EXPIRED) must not transition to anything else
    assert not RecoveryStateMachine.can_transition(RecoveryState.RECOVERED, RecoveryState.SCHEDULED_RETRY)
    assert not RecoveryStateMachine.can_transition(RecoveryState.CANCELLED, RecoveryState.LINK_SENT)
    assert not RecoveryStateMachine.can_transition(RecoveryState.EXPIRED, RecoveryState.IN_GRACE_WINDOW)

    with pytest.raises(InvalidStateTransitionError):
        RecoveryStateMachine.validate_transition(RecoveryState.RECOVERED, RecoveryState.SCHEDULED_RETRY)


def test_terminal_state_detection():
    assert RecoveryStateMachine.is_terminal(RecoveryState.RECOVERED)
    assert RecoveryStateMachine.is_terminal(RecoveryState.CANCELLED)
    assert RecoveryStateMachine.is_terminal(RecoveryState.EXPIRED)
    assert not RecoveryStateMachine.is_terminal(RecoveryState.TRIAGING)
    assert not RecoveryStateMachine.is_terminal(RecoveryState.IN_GRACE_WINDOW)
    assert not RecoveryStateMachine.is_terminal(RecoveryState.SCHEDULED_RETRY)
