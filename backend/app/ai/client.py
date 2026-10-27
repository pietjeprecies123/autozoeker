"""Shared Claude API helpers. Everything AI is optional: without ANTHROPIC_API_KEY these raise AiUnavailable."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import get_settings

log = logging.getLogger(__name__)

# $ per million tokens (input, output) – keep in sync with https://platform.claude.com/docs/en/about-claude/pricing
PRICING = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-1": (10.0, 50.0),
}
WEB_SEARCH_PER_1000 = 10.0
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Server-side refusal fallbacks are available for these models (not for Haiku).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}


class AiUnavailable(Exception):
    pass


class AiRefused(Exception):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    web_searches: int = 0

    def add(self, usage) -> None:
        if usage is None:
            return
        self.input_tokens += (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        stu = getattr(usage, "server_tool_use", None)
        if stu is not None:
            self.web_searches += getattr(stu, "web_search_requests", 0) or 0

    def cost_usd(self, model: str) -> float | None:
        price = PRICING.get(model)
        if not price:
            return None
        return round(self.input_tokens / 1e6 * price[0] + self.output_tokens / 1e6 * price[1]
                     + self.web_searches / 1000 * WEB_SEARCH_PER_1000, 4)


def get_client():
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AiUnavailable("Stel ANTHROPIC_API_KEY in om AI-functies te gebruiken.")
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=300.0)


def request_kwargs(model: str) -> dict:
    """Common kwargs for client.beta.messages.create: refusal fallback where supported."""
    if model in FALLBACK_MODELS:
        return {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    return {}


def text_of(response) -> str:
    return "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text")
