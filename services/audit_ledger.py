import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


class AuditLedgerService:
    """
    Cryptographic Immutable Audit Ledger for Financial Decision Traces.
    Constructs a SHA-256 hash chain across all recovery decisions,
    guaranteeing non-repudiation and tamper detection.
    """

    GENESIS_HASH = "0" * 64

    @classmethod
    def calculate_record_hash(
        cls,
        prev_hash: Optional[str],
        case_id: str,
        step_number: int,
        agent_mode: str,
        final_action: str,
        diagnosis: Dict[str, Any],
        policy_checks: Any,
        execution_result: Optional[Dict[str, Any]],
        created_at_str: str,
    ) -> str:
        payload_repr = {
            "prev_hash": prev_hash or cls.GENESIS_HASH,
            "case_id": case_id,
            "step_number": step_number,
            "agent_mode": agent_mode,
            "final_action": final_action,
            "diagnosis": diagnosis,
            "policy_checks": policy_checks,
            "execution_result": execution_result,
            "created_at": created_at_str,
        }
        serialized = json.dumps(payload_repr, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def verify_chain_integrity(cls, traces: List[Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates the cryptographic integrity of an ordered sequence of decision traces.
        """
        if not traces:
            return True, None

        prev_expected = cls.GENESIS_HASH
        for i, trace in enumerate(traces):
            current_prev = trace.prev_hash or cls.GENESIS_HASH
            if i == 0 and current_prev != cls.GENESIS_HASH:
                return False, f"Trace 0 prev_hash mismatch: expected {cls.GENESIS_HASH}, got {current_prev}"
            elif i > 0 and current_prev != prev_expected:
                return False, f"Trace {i} prev_hash mismatch: expected {prev_expected}, got {current_prev}"

            computed_hash = cls.calculate_record_hash(
                prev_hash=current_prev,
                case_id=str(trace.case_id),
                step_number=trace.step_number,
                agent_mode=trace.agent_mode,
                final_action=trace.final_action,
                diagnosis=trace.diagnosis,
                policy_checks=trace.policy_checks,
                execution_result=trace.execution_result,
                created_at_str=str(trace.created_at),
            )

            if trace.record_hash and trace.record_hash != computed_hash:
                return (
                    False,
                    f"Trace {i} record_hash tampered: expected {computed_hash}, got {trace.record_hash}",
                )

            prev_expected = computed_hash

        return True, None


# Global singleton instance
audit_ledger = AuditLedgerService()
