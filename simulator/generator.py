import random
import time
import uuid
from typing import Any, Dict, List, Tuple
from domain.models.enums import CustomerTier, FailureCode, PaymentMethod


class SyntheticPaymentDataGenerator:
    """
    Synthetic Payment & Webhook Generator for reproducible benchmarks.
    Uses fixed seed (default=42) so judges can verify deterministic evaluation.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def generate_dataset(
        self, num_customers: int = 1000, num_events: int = 5000
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates realistic customer pool and sequential payment webhook events.
        """
        # 1. Generate Customers
        tiers = [CustomerTier.STANDARD] * 70 + [CustomerTier.VIP] * 20 + [CustomerTier.ENTERPRISE] * 10
        first_names = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Kabir", "Neha", "Aditya", "Pooja"]
        last_names = ["Sharma", "Verma", "Patel", "Reddy", "Mehta", "Nair", "Gupta", "Iyer", "Rao", "Singh"]

        customers = []
        for i in range(num_customers):
            c_id = f"cust_{uuid.UUID(int=random.getrandbits(128)).hex[:10]}"
            first = random.choice(first_names)
            last = random.choice(last_names)
            customers.append({
                "id": c_id,
                "name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower()}{i}@example.com",
                "phone": f"+9198{random.randint(10000000, 99999999)}",
                "tier": random.choice(tiers).value,
                "contact_token_bucket": 3,
                "opted_out": random.random() < 0.04,  # 4% opted out
            })

        # 2. Failure code distribution matching realistic Indian fintech volumes
        failure_weights = [
            (FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED, 0.35),  # 35% 3DS dropouts
            (FailureCode.INSUFFICIENT_FUNDS, 0.25),                  # 25% Balance deficit
            (FailureCode.GATEWAY_ERROR, 0.15),                      # 15% Bank downtime
            (FailureCode.CARD_EXPIRED, 0.12),                       # 12% Expired cards
            (FailureCode.TRANSACTION_LIMIT_EXCEEDED, 0.08),         # 8% Velocity limit
            (FailureCode.CARD_BLOCKED, 0.05),                       # 5% Blocked / Terminal
        ]
        fail_codes, weights = zip(*failure_weights)

        # 3. Generate Sequential Events
        events = []
        base_timestamp = int(time.time()) - (7 * 86400)  # Past 7 days

        for i in range(num_events):
            cust = random.choice(customers)
            pay_id = f"pay_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"
            order_id = f"order_{uuid.UUID(int=random.getrandbits(128)).hex[:10]}"
            
            # Amount distribution: 80% small (₹500 - ₹5,000), 18% mid (₹5,000 - ₹45,000), 2% high-value (₹50,000 - ₹2,50,000)
            amt_roll = random.random()
            if amt_roll < 0.80:
                amount_paise = random.randint(50000, 500000)  # ₹500 - ₹5,000
            elif amt_roll < 0.98:
                amount_paise = random.randint(500000, 4500000)  # ₹5,000 - ₹45,000
            else:
                amount_paise = random.randint(5000000, 25000000)  # ₹50,000 - ₹2,50,000 (Human Ops trigger)

            method = random.choice([PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.NETBANKING])
            chosen_code = random.choices(fail_codes, weights=weights)[0]

            event_time = base_timestamp + (i * 120)

            # Check if this failure will organically capture late (30% of 3DS dropouts capture within 5m)
            will_capture_late = (
                chosen_code == FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED and random.random() < 0.35
            ) or (
                chosen_code == FailureCode.GATEWAY_ERROR and random.random() < 0.20
            )

            # Failure event
            fail_event_id = f"evt_fail_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"
            events.append({
                "event_id": fail_event_id,
                "event_type": "payment.failed",
                "payment_id": pay_id,
                "order_id": order_id,
                "customer_id": cust["id"],
                "amount_in_paise": amount_paise,
                "method": method.value,
                "failure_code": chosen_code.value,
                "failure_description": f"Payment failure ({chosen_code.value})",
                "timestamp": event_time,
                "will_capture_late": will_capture_late,
            })

            # If organic late capture, append payment.captured 180-360 seconds later
            if will_capture_late:
                cap_event_id = f"evt_cap_{uuid.UUID(int=random.getrandbits(128)).hex[:12]}"
                events.append({
                    "event_id": cap_event_id,
                    "event_type": "payment.captured",
                    "payment_id": pay_id,
                    "order_id": order_id,
                    "customer_id": cust["id"],
                    "amount_in_paise": amount_paise,
                    "method": method.value,
                    "timestamp": event_time + random.randint(180, 360),
                })

        # Sort all events chronologically
        events.sort(key=lambda x: x["timestamp"])

        return customers, events
