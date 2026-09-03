from datetime import datetime, timedelta
from typing import List, Optional, Union

from domain.models.entities import CustomerEntity
from domain.policies.engine import policy_engine


def _parse_ts(value: Union[str, datetime]) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return datetime.utcnow()


def refresh_contact_window(customer: CustomerEntity, now: Optional[datetime] = None) -> List[str]:
    """Drop contact timestamps older than the fatigue window and refill the token bucket."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(hours=policy_engine.MAX_CONTACTS_WINDOW_HOURS)
    raw = customer.contact_timestamps or []
    kept: List[datetime] = []
    for item in raw:
        ts = _parse_ts(item)
        if ts >= cutoff:
            kept.append(ts)
    customer.contact_timestamps = [ts.isoformat() for ts in kept]
    used = len(kept)
    customer.contact_token_bucket = max(0, policy_engine.MAX_CONTACTS_PER_WINDOW - used)
    return customer.contact_timestamps


def record_contact(customer: CustomerEntity, now: Optional[datetime] = None) -> None:
    now = now or datetime.utcnow()
    refresh_contact_window(customer, now)
    stamps = list(customer.contact_timestamps or [])
    stamps.append(now.isoformat())
    customer.contact_timestamps = stamps
    customer.last_contacted_at = now
    customer.contact_token_bucket = max(0, policy_engine.MAX_CONTACTS_PER_WINDOW - len(stamps))


def timestamps_as_datetimes(customer: CustomerEntity) -> List[datetime]:
    return [_parse_ts(item) for item in (customer.contact_timestamps or [])]
