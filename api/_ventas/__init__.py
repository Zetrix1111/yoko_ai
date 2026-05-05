"""Helpers compartidos entre los handlers de ventas."""

from datetime import datetime, timezone


def now_iso() -> str:
    """Timestamp UTC ISO-8601 (con zona). Usado en created_at / last_message_at."""
    return datetime.now(timezone.utc).isoformat()
