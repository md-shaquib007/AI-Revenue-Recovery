from datetime import datetime
from services.audit_ledger import audit_ledger


class MockTrace:
    def __init__(self, step_number, agent_mode, final_action, diagnosis, policy_checks, execution_result, prev_hash=None, created_at=None):
        self.case_id = "case_test_audit_01"
        self.step_number = step_number
        self.agent_mode = agent_mode
        self.final_action = final_action
        self.diagnosis = diagnosis
        self.policy_checks = policy_checks
        self.execution_result = execution_result
        self.prev_hash = prev_hash or audit_ledger.GENESIS_HASH
        self.created_at = created_at or datetime.utcnow()
        self.record_hash = audit_ledger.calculate_record_hash(
            prev_hash=self.prev_hash,
            case_id=self.case_id,
            step_number=self.step_number,
            agent_mode=self.agent_mode,
            final_action=self.final_action,
            diagnosis=self.diagnosis,
            policy_checks=self.policy_checks,
            execution_result=self.execution_result,
            created_at_str=str(self.created_at),
        )


def test_valid_audit_hash_chain():
    t1 = MockTrace(
        step_number=1,
        agent_mode="AI_REASONER",
        final_action="WAIT",
        diagnosis={"reason": "3DS Dropout"},
        policy_checks=[{"rule_name": "NO_OP_ON_CAPTURED", "passed": True}],
        execution_result={"delay": 480},
    )
    t2 = MockTrace(
        step_number=2,
        agent_mode="AI_REASONER",
        final_action="PAYMENT_LINK",
        diagnosis={"reason": "Grace expired"},
        policy_checks=[{"rule_name": "FATIGUE_TOKEN_BUDGET", "passed": True}],
        execution_result={"plink": "https://rzp.io/i/test"},
        prev_hash=t1.record_hash,
    )
    t3 = MockTrace(
        step_number=3,
        agent_mode="AI_REASONER",
        final_action="CANCEL_RECOVERY",
        diagnosis={"reason": "Captured late"},
        policy_checks=[{"rule_name": "NO_OP_ON_CAPTURED", "passed": True}],
        execution_result={"status": "cancelled"},
        prev_hash=t2.record_hash,
    )

    traces = [t1, t2, t3]
    is_valid, error = audit_ledger.verify_chain_integrity(traces)
    assert is_valid is True
    assert error is None


def test_audit_hash_chain_tamper_detection():
    t1 = MockTrace(
        step_number=1,
        agent_mode="AI_REASONER",
        final_action="WAIT",
        diagnosis={"reason": "3DS Dropout"},
        policy_checks=[{"rule_name": "NO_OP_ON_CAPTURED", "passed": True}],
        execution_result={"delay": 480},
    )
    t2 = MockTrace(
        step_number=2,
        agent_mode="AI_REASONER",
        final_action="PAYMENT_LINK",
        diagnosis={"reason": "Grace expired"},
        policy_checks=[{"rule_name": "FATIGUE_TOKEN_BUDGET", "passed": True}],
        execution_result={"plink": "https://rzp.io/i/test"},
        prev_hash=t1.record_hash,
    )

    # Malicious actor tampers with t1 diagnosis
    t1.diagnosis = {"reason": "Unauthorized charge altered"}

    traces = [t1, t2]
    is_valid, error = audit_ledger.verify_chain_integrity(traces)
    assert is_valid is False
    assert "tampered" in error
