"""Helpers compartidos entre los handlers de ventas."""

import os
from datetime import datetime, timezone

_FALLBACK_TENANT = "cmejia"


def tenant_id() -> str:
    """Tenant activo según TENANT_ID env, con fallback a 'cmejia'."""
    return os.environ.get("TENANT_ID") or _FALLBACK_TENANT


def now_iso() -> str:
    """Timestamp UTC ISO-8601 (con zona). Usado en created_at / last_message_at."""
    return datetime.now(timezone.utc).isoformat()
