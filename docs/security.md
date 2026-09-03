# REVIVE: Security & Compliance Architecture

## Threat Model Overview

| Threat Vector | Risk | Mitigation Layer |
|---|---|---|
| Forged webhooks | HIGH | HMAC-SHA256 signature verification |
| Replay attacks | HIGH | Configurable timestamp tolerance window |
| Prompt injection via payment notes | HIGH | Regex + token cleansing firewall |
| PII leakage to external AI | HIGH | Email, phone, name masking |
| Race conditions under concurrency | HIGH | Per-payment async mutex lock |
| Tampered audit records | HIGH | SHA-256 hash-chained decision ledger |
| LLM issuing financial actions | CRITICAL | Policy firewall has sole financial authority |
| High-value unauthorized charges | CRITICAL | ₹50,000 gate → mandatory human sign-off |
| Duplicate payment charges | HIGH | Idempotency keys on all Razorpay API calls |
| Unauthorized operator access | HIGH | JWT + RBAC on all ops routes |
| DoS via webhook flood | MEDIUM | In-memory rate limiter middleware |
| Customer contact spam | MEDIUM | Token-bucket fatigue window (2 pings / 48h) |
| Opted-out customer contact | MEDIUM | Opt-out flag hard-blocked at policy layer |

---

## 1. Webhook Security (Multi-Layer)

### 1.1 HMAC-SHA256 Signature Verification
Every inbound request to `POST /api/v1/webhooks/razorpay` is cryptographically validated using HMAC-SHA256 against `x-razorpay-signature`. Unsigned or tampered payloads are rejected at the edge with **HTTP 401**.

The bypass (`x-revive-dev-bypass`) is only enabled when `APP_ENV=development` and is completely inert in production.

### 1.2 Replay Attack Defense
When `ENFORCE_REPLAY_WINDOW=true`, any webhook with a `created_at` timestamp older than `WEBHOOK_REPLAY_TOLERANCE_SECONDS` (default: 300s) is rejected with **HTTP 400**:
```
"Webhook timestamp outside acceptable replay window tolerance"
```
This prevents adversaries from capturing and replaying legitimate signed webhooks.

### 1.3 Idempotency Deduplication
`webhook_events.event_id` has a unique database constraint. Any duplicate delivery of the same event (from Razorpay's retry policies) returns `200 DUPLICATE_IGNORED` without re-processing. The `IntegrityError` path handles concurrent race conditions on insertion.

---

## 2. Concurrency & Race Condition Prevention

### 2.1 Per-Payment Distributed Mutex
`services/lock_manager.py` provides an `asyncio.Lock`-based per-key mutex. The correlation engine wraps all payment processing in:
```python
async with lock_manager.acquire(f"payment:{payment_id}"):
    ...
```
This guarantees that a simultaneous `payment.failed` + `payment.captured` event pair for the same payment is processed strictly in sequence. Different payments execute fully in parallel.

### 2.2 Optimistic Concurrency Control
`RecoveryCaseEntity.version` is incremented on every state change. Concurrent modification attempts will produce version mismatches, making conflicts detectable.

### 2.3 Database Connection Pool
`services/db.py` configures:
- `pool_size=50` — Baseline connections ready at all times
- `max_overflow=100` — Burst capacity (up to 150 total connections)
- `pool_pre_ping=True` — Validates connections before use
- `pool_recycle=3600` — Prevents stale connection errors

---

## 3. Cryptographic Audit Ledger

Every decision trace is chained via SHA-256:

```
Genesis Hash: "0" × 64

trace_1.record_hash = SHA256(
    GENESIS_HASH + case_id + step_number + agent_mode +
    final_action + diagnosis + policy_checks + execution_result + created_at
)

trace_2.record_hash = SHA256(
    trace_1.record_hash + case_id + step_number + ...
)
```

**Properties:**
- Any retroactive modification to any historical trace breaks all subsequent hashes.
- Tampering is immediately detectable via `audit_ledger.verify_chain_integrity()`.
- Exposed via `GET /api/v1/recovery/cases/{id}/audit-verification`.
- Case detail endpoint (`GET /api/v1/recovery/cases/{id}`) includes `audit_chain_verified: true/false` inline.

---

## 4. Prompt Injection Defense (Zero-Trust Metadata)

Customer notes, failure descriptions, and payment metadata are classified as **Untrusted Data**. The `PolicyEngine` enforces:

1. **Regex cleansing** — Strips common injection patterns (`ignore previous`, `pretend you are`, `system:`, etc.)
2. **Token allowlisting** — Only alphanumeric + limited punctuation passes through
3. **Structural isolation** — Untrusted data never injected into the system prompt role

Tested by `tests/unit/test_policy_engine.py::test_prompt_injection_sanitization` and `tests/chaos/test_chaos_scenarios.py::test_chaos_prompt_injection_defense`.

---

## 5. PII Protection

Before any external LLM API call, all customer PII is masked:

| Field | Input Example | Masked Output |
|---|---|---|
| Email | `john.doe@razorpay.com` | `j*****e@razorpay.com` |
| Phone | `+919876543210` | `+919*******10` |
| Name | `Vikram Sharma` | `V***** S*****` |

Implemented in `domain/policies/engine.py` via `mask_email()`, `mask_phone()`, `mask_name()` static methods. Tested in `tests/unit/test_security_hardening.py`.

---

## 6. Financial Authority Model

The AI agent is **strictly non-custodial**:
- Cannot issue refunds
- Cannot modify billing amounts
- Cannot cancel subscriptions
- Cannot initiate charges without policy approval

**Financial actions flow:**
```
AI proposes action → Policy Engine evaluates → Approved or Escalated
                                    ↓
                         Systems execute (Razorpay API)
```

**High-Value Safety Gate:**  
Transactions ≥ ₹50,000 automatically trigger the High-Value Safety Gate, routing the case to the Human Ops Review Queue. No automated action is taken until an operator provides explicit sign-off via `POST /api/v1/human-ops/cases/{id}/decision`.

---

## 7. Customer Fatigue & Privacy Protection

- **Token-bucket rate limiting** enforces a hard ceiling of max 2 communications per customer in any 48-hour rolling window.
- Customers with `opted_out = true` are immediately blocked from all outbound messaging channels (WhatsApp/SMS/Email links).
- Contact timestamps are stored and validated on every potential outbound action.

---

## 8. Operator Access Control (RBAC)

When `AUTH_REQUIRED=true` or `APP_ENV=production`:
- All operator routes require a valid JWT bearer token.
- Tokens issued by `POST /api/v1/auth/login` with operator credentials.
- `require_operator` dependency enforces authentication on Human Ops, Recovery, Intel, Chaos, and Benchmark routes.
- Default credentials: `ops` / `revive-ops-2026` (must be overridden in production via `OPERATOR_USERNAME` / `OPERATOR_PASSWORD` env vars).

---

## 9. Production Hardening Checklist

Before deploying to production:

- [ ] Set `APP_ENV=production`
- [ ] Set `AUTH_REQUIRED=true`
- [ ] Set `RAZORPAY_WEBHOOK_SECRET` to live webhook signing secret
- [ ] Set `JWT_SECRET` to a strong random secret (≥64 chars)
- [ ] Set `ENFORCE_REPLAY_WINDOW=true`
- [ ] Set `CHAOS_ENABLED=false` (default)
- [ ] Change default operator password from `revive-ops-2026`
- [ ] Use PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`)
- [ ] Enable DB SSL (`?ssl=require` in connection string)
- [ ] Configure backup schedule (`scripts/backup.sh`)
- [ ] Set `SENTRY_DSN` for error tracking
