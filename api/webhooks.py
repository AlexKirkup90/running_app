"""Webhook registry for real-time event notifications.

Coaches and integrations can register URLs to receive POST callbacks
when key events occur (new check-in, session logged, intervention created, etc.).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# In-memory registry (upgrade to DB table for production persistence)
_webhooks: dict[str, dict] = {}

VALID_EVENTS = {
    "checkin.created",
    "training_log.created",
    "intervention.created",
    "intervention.closed",
    "plan.published",
    "athlete.created",
}


def register_webhook(url: str, events: list[str], secret: str | None = None) -> dict:
    """Register a new webhook endpoint for specified events."""
    invalid = set(events) - VALID_EVENTS
    if invalid:
        raise ValueError(f"Invalid events: {invalid}. Valid: {sorted(VALID_EVENTS)}")
    hook_id = uuid4().hex[:12]
    _webhooks[hook_id] = {"id": hook_id, "url": url, "events": events, "secret": secret, "active": True}
    logger.info("Webhook registered: id=%s url=%s events=%s", hook_id, url, events)
    return _webhooks[hook_id]


def unregister_webhook(hook_id: str) -> bool:
    """Remove a webhook by ID. Returns True if found and removed."""
    if hook_id in _webhooks:
        del _webhooks[hook_id]
        logger.info("Webhook unregistered: id=%s", hook_id)
        return True
    return False


def list_webhooks() -> list[dict]:
    """Return all registered webhooks."""
    return list(_webhooks.values())


def _sign_payload(payload: str, secret: str) -> str:
    """HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def dispatch_event(event_type: str, data: dict[str, Any]) -> int:
    """Fire webhook callbacks for an event type. Returns count of dispatches sent."""
    subscribers = [h for h in _webhooks.values() if h["active"] and event_type in h["events"]]
    if not subscribers:
        return 0

    payload = json.dumps({"event": event_type, "data": data}, default=str)
    dispatched = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for hook in subscribers:
            headers = {"Content-Type": "application/json", "X-Webhook-Event": event_type}
            if hook.get("secret"):
                headers["X-Webhook-Signature"] = _sign_payload(payload, hook["secret"])
            try:
                resp = await client.post(hook["url"], content=payload, headers=headers)
                logger.info("Webhook dispatched: id=%s event=%s status=%d", hook["id"], event_type, resp.status_code)
                dispatched += 1
            except Exception as e:
                logger.warning("Webhook delivery failed: id=%s url=%s error=%s", hook["id"], hook["url"], e)
    return dispatched
