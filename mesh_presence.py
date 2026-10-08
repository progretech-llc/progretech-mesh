"""Expire activity evidence independently of transport connectivity."""
from datetime import datetime, timezone
import math
import time

ACTIVITY_TTL_SECONDS = 180

def observed_state(record, now=None):
    state = record.get('state', 'unknown')
    if state not in {'active', 'working', 'processing'}:
        return state
    activity = record.get('activity') or {}
    value = activity.get('observed_at') or record.get('last_heartbeat')
    try:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                return 'unknown'
            at = parsed.timestamp()
        else:
            at = float(value)
        age = (time.time() if now is None else now) - at
        if not math.isfinite(age) or not 0 <= age <= ACTIVITY_TTL_SECONDS:
            return 'unknown'
    except (TypeError, ValueError, OverflowError):
        return 'unknown'
    return state
