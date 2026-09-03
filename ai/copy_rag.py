import math
from typing import Any, Dict, List, Optional
from domain.models.enums import FailureCode


# Historical top-converting recovery copy vector embeddings DB
HIGH_CONVERTING_COPY_CORPUS = [
    {
        "id": "copy_nsf_001",
        "category": FailureCode.INSUFFICIENT_FUNDS.value,
        "copy_headline": "Special Offer: Pay now & save ₹50 on your renewal.",
        "conversion_rate": 0.42,
        "vector": [0.85, 0.12, 0.45, 0.90],
    },
    {
        "id": "copy_auth_001",
        "category": FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED.value,
        "copy_headline": "Your bank requires 1-click verification to complete your subscription.",
        "conversion_rate": 0.58,
        "vector": [0.20, 0.92, 0.30, 0.75],
    },
    {
        "id": "copy_timeout_001",
        "category": FailureCode.BAD_REQUEST_PAYMENT_TIMED_OUT.value,
        "copy_headline": "Your payment timed out at bank. Tap here to retry instantly via UPI.",
        "conversion_rate": 0.51,
        "vector": [0.40, 0.55, 0.88, 0.60],
    },
    {
        "id": "copy_expired_001",
        "category": FailureCode.CARD_EXPIRED.value,
        "copy_headline": "Your card has expired. Update details in 10 seconds to keep access.",
        "conversion_rate": 0.47,
        "vector": [0.10, 0.30, 0.20, 0.95],
    },
]


class SemanticCopyRAG:
    """
    Semantic Copy Vector Similarity Retrieval Engine (RAG).

    Retrieves top-performing historical recovery communication copy matching
    the payment's failure code and customer context to maximize conversion.
    """

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        return dot / max(1e-6, (norm1 * norm2))

    def retrieve_best_copy(
        self,
        failure_code: Optional[FailureCode],
        query_vector: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        fc_str = failure_code.value if failure_code else FailureCode.INSUFFICIENT_FUNDS.value
        query = query_vector or [0.5, 0.5, 0.5, 0.5]

        best_match = None
        highest_sim = -1.0

        for item in HIGH_CONVERTING_COPY_CORPUS:
            sim = self._cosine_similarity(query, item["vector"])
            # Boost score if failure code category matches exactly
            if item["category"] == fc_str:
                sim += 0.25

            if sim > highest_sim:
                highest_sim = sim
                best_match = item

        if not best_match:
            best_match = HIGH_CONVERTING_COPY_CORPUS[0]

        return {
            "copy_id": best_match["id"],
            "copy_headline": best_match["copy_headline"],
            "historical_conversion_rate": best_match["conversion_rate"],
            "similarity_score": round(min(1.0, highest_sim), 3),
        }


# Global singleton instance
copy_rag = SemanticCopyRAG()
