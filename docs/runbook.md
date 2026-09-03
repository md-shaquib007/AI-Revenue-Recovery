# REVIVE: Operational Runbook

## Daily Health Checks

1. Confirm `GET /ready` returns `{"database": "ok"}`.
2. Confirm `GET /metrics` shows `revive_worker_ticks_total` increasing every `WORKER_INTERVAL_SECONDS`.
3. Review Human Ops queue (`GET /api/v1/human-ops/queue`) for escalated invoices ≥ ₹50,000.
4. Check `GET /api/v1/intel/pulse` for bank health degradation signals.
5. Spot-check `audit_chain_verified: true` on recent recovery cases.

---

## Starting the System

```bash
# Backend
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Frontend Command Center
cd apps/web && npm run start

# Docker (recommended for production)
docker compose up -d
```

---

## Common Incidents & Responses

### Razorpay Gateway Down
1. REVIVE continues ingesting webhooks; failed processing marks `webhook_events.status=FAILED` — Razorpay will retry the delivery automatically.
2. Outbound payment links fail closed; the worker records a trace and retries at the next tick.
3. `GET /api/v1/intel/pulse` will reflect degraded bank health scores.
4. **Do not disable the policy firewall.**

### LLM API Down (OpenAI / Gemini)
- The heuristic/deterministic fallback engine activates automatically with 0 downtime.
- Chaos toggle `POST /api/v1/chaos/simulate {"scenario": "llm_outage"}` can simulate this in non-production.
- Verify fallback is active by checking `agent_mode: DETERMINISTIC_FALLBACK` in decision traces.

### Worker Stuck / Not Processing
```bash
# Check tick counter
curl http://localhost:8000/metrics | grep revive_worker_ticks_total

# Manually drain one tick (requires auth)
curl -X POST http://localhost:8000/api/v1/recovery/worker/tick \
  -H "Authorization: Bearer <token>"
```
- Check `RecoveryCaseEntity.next_action_at` on open cases.
- If all cases have `next_action_at = null`, worker has nothing to process.

### High Concurrency / Webhook Flood
- Per-payment mutex ensures correctness; no manual intervention needed.
- Monitor `revive_webhook_duplicate_total` — normal during Razorpay retry storms.
- Monitor `revive_rate_limited_total` — increase `RATE_LIMIT_MAX_REQUESTS` if operators are being throttled.

### Audit Chain Integrity Failure
```bash
# Verify a specific case
curl http://localhost:8000/api/v1/recovery/cases/{case_id}/audit-verification \
  -H "Authorization: Bearer <token>"

# Response: {"is_tamper_free": false, "error": "Step 3 tampered: ..."}
```
- Immediately quarantine the affected case.
- Pull DB backup for forensics: `backups/revive_<stamp>.dump`
- Do not allow operator actions on the affected case until forensics complete.

### Replay Attack Detected
- Check logs for `"message": "webhook_replay_rejected"` events.
- Review `ENFORCE_REPLAY_WINDOW` and `WEBHOOK_REPLAY_TOLERANCE_SECONDS` settings.
- If attacks are persistent, tighten the tolerance window and alert security team.

### Database Connection Exhaustion
- Monitor Postgres `max_connections` vs `pool_size + max_overflow = 150`.
- If DB connections saturate: reduce `DB_MAX_OVERFLOW`, scale Postgres, or add a PgBouncer connection pooler.
- `pool_pre_ping=True` auto-recovers stale connections.

---

## Manual Worker Trigger (Drain Due Cases)

```bash
# Trigger one worker tick manually (authenticated)
curl -X POST http://localhost:8000/api/v1/recovery/worker/tick \
  -H "Authorization: Bearer $(TOKEN)"
```

---

## Backup & Restore (PostgreSQL)

### Backup
```bash
bash scripts/backup.sh
# Creates: backups/revive_<timestamp>.dump
```

### Restore
```bash
pg_restore -h $POSTGRES_HOST -U revive -d revive --clean backups/revive_<stamp>.dump
```

---

## Metrics Reference

| Metric | Counter Name | Meaning |
|---|---|---|
| Webhooks received | `revive_webhook_received_total` | Total webhooks ingested |
| Webhooks duplicate | `revive_webhook_duplicate_total` | Duplicate event_ids ignored |
| Webhooks failed | `revive_webhook_failed_total` | Dead-letter path errors |
| Worker ticks | `revive_worker_ticks_total` | Background loop iterations |
| Worker actions | `revive_worker_actions_total` | Recovery actions executed |
| Policy vetoes | `revive_policy_veto_total` | AI proposals overridden by policy |
| Rate limited | `revive_rate_limited_total` | Requests throttled |
| Strategy cache hits | `revive_strategy_cache_hits_total` | AI decisions served from cache |
| Audit verifications | `revive_audit_verifications_total` | Chain integrity checks run |

---

## Configuration Quick Reference

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` for production |
| `AUTH_REQUIRED` | `false` | Set `true` in production |
| `ENFORCE_REPLAY_WINDOW` | `false` | Set `true` in production |
| `WEBHOOK_REPLAY_TOLERANCE_SECONDS` | `300` | 5 minutes |
| `STRATEGY_CACHE_ENABLED` | `true` | Disable only for debugging |
| `AI_TIMEOUT_SECONDS` | `1.5` | LLM call budget |
| `WORKER_INTERVAL_SECONDS` | `30` | Recovery worker tick frequency |
| `DB_POOL_SIZE` | `50` | SQLAlchemy pool size |
| `DB_MAX_OVERFLOW` | `100` | Burst connection capacity |

---

## Escalation Contacts

Update this section with your team's on-call contacts before going to production.

- **Engineering On-Call:** (add contact)
- **Razorpay Partner Support:** merchant.support@razorpay.com
- **Database DBA:** (add contact)
