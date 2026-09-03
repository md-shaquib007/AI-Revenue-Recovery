# REVIVE Architecture & API Reference Manual

> **System Axiom:** *"AI proposes. Policy decides. Systems execute."*

---

## 1. System Topology Overview

REVIVE is built as an event-driven microservices architecture using FastAPI, SQLAlchemy Async, Next.js 14, and PyTest.

![REVIVE Software Architecture Diagram](C:\Users\Laptop\.gemini\antigravity\brain\a59c607c-5dba-4adf-8abc-839f3406e694\revive_architecture_final_1787734613495.jpg)

---

## 2. Core Modules Reference

### 2.1 Multi-Agent Shadow Simulator ([`ai/shadow_simulator.py`](file:///d:/AI%20Revenue%20Recovery/ai/shadow_simulator.py))
- Evaluates candidate actions against 50 parallel prospective customer personas.
- Keyed with deterministic seeded RNG `hash(payment_id:action)`.
- If friction score $> 45\%$, calls `best_alternative_action()` and auto-pivots action before execution.

### 2.2 Predictive Bank Outage Sentinel ([`domain/bank_health/sentinel.py`](file:///d:/AI%20Revenue%20Recovery/domain/bank_health/sentinel.py))
- Monitors failure velocity ($\frac{dF}{dt}$) over 3-minute sliding windows.
- Triggers Rule 7 policy cool-off when velocity $\ge 3.5\text{ failures/min}$.
- Self-heals on `payment.captured` events via `record_success()`.

### 2.3 Contextual Multi-Armed Bandit ([`ai/bandit.py`](file:///d:/AI%20Revenue%20Recovery/ai/bandit.py))
- Uses Thompson Sampling with Beta distributions $B(\alpha, \beta)$ per `(failure_code, bank_key, customer_tier)` segment.
- Dynamically learns recovery probabilities $P_{\text{learned}}$ from real-world payment outcomes.

### 2.4 Multi-Gateway Fallback Router ([`services/gateway_adapter.py`](file:///d:/AI%20Revenue%20Recovery/services/gateway_adapter.py))
- Routes link generation to Cashfree / PayU fallback when Razorpay Sentinel circuit is open.

### 2.5 Native WhatsApp 1-Click UPI Deep Links ([`services/whatsapp_service.py`](file:///d:/AI%20Revenue%20Recovery/services/whatsapp_service.py))
- Formats standard NPCI `upi://pay?pa=...` deep links and builds WhatsApp Business API template payloads.

### 2.6 Cryptographic Audit Ledger ([`services/audit_ledger.py`](file:///d:/AI%20Revenue%20Recovery/services/audit_ledger.py))
- SHA-256 hash chaining (`prev_hash` $\to$ `record_hash`) across all decision traces.

---

## 3. Complete API Specification

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/webhooks/razorpay` | Ingests Razorpay webhook events with HMAC verification & replay defense |
| `GET` | `/api/v1/intel/sentinel` | Returns predictive bank downtime risk scores |
| `POST` | `/api/v1/intel/shadow-sim` | Executes 50-persona shadow simulation for a payment |
| `POST` | `/api/v1/intel/evaluate-offer` | Evaluates dynamic micro-discount offer Net EV |
| `GET` | `/api/v1/recovery/cases/{id}` | Fetches full case details and inline SHA-256 audit verification |
| `GET` | `/api/v1/recovery/cases/{id}/audit-verification` | Cryptographic audit chain verification |
| `POST` | `/api/v1/ops/cases/{id}/approve` | Human Operator governance approval gate |
| `GET` | `/health`, `/ready`, `/metrics` | Production health probes & Prometheus text metrics |
