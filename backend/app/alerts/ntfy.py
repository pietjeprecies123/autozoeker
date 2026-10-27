"""ntfy.sh push notifications (https://docs.ntfy.sh/publish/) using JSON publishing."""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


def build_payload(topic: str, title: str, message: str, click: str | None = None, attach: str | None = None,
                  tags: list[str] | None = None, priority: int = 3, actions: list[dict] | None = None) -> dict:
    payload: dict = {"topic": topic, "title": title[:250], "message": message[:4000], "priority": priority,
                     "markdown": True}
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    if attach:
        payload["attach"] = attach
    if actions:
        payload["actions"] = actions[:3]
    return payload


def publish(payload: dict, client: httpx.Client | None = None) -> bool:
    settings = get_settings()
    if not payload.get("topic"):
        return False
    headers = {}
    if settings.ntfy_token:
        headers["Authorization"] = f"Bearer {settings.ntfy_token}"
    try:
        c = client or httpx.Client(timeout=10.0)
        resp = c.post(settings.ntfy_server.rstrip("/"), json=payload, headers=headers)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("ntfy publish failed: %s", exc)
        return False
