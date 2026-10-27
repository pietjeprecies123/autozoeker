"""Claude integrations with a stubbed client (no network, no API key)."""

import json
from types import SimpleNamespace as NS

import pytest

from app.ai import ad_scan, nl_search, research
from app.ai.client import AiRefused, AiUnavailable, Usage, get_client
from app.models import IssueResearch, Listing

RESULT = {
    "summary": "Betrouwbaar, let op de koppeling.",
    "battery_warranty": None,
    "general_checks": ["Check de koppeling"],
    "issues": [{
        "title": "Koppeling slijt snel", "severity": "medium", "likelihood": "medium", "category": "transmissie",
        "years_from": 2017, "years_to": None, "engine_keywords": ["1.0"], "fuels": ["benzine"],
        "summary": "Snel slijtende koppeling.", "symptoms": ["Slippen"], "repair_cost_min": 600, "repair_cost_max": 900,
        "fix_type": "maintenance", "fix_description": "Vervangen", "verify": ["Factuur"],
        "questions": ["Is de koppeling vervangen?"], "test_drive": ["Optrekken in 4"],
        "sources": [{"title": "Bron", "url": "https://example.org"}],
    }],
}


class StubMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def stub(*responses):
    msgs = StubMessages(responses)
    return NS(beta=NS(messages=msgs)), msgs


def usage(i=1000, o=500, s=0):
    return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=0, cache_creation_input_tokens=0,
              server_tool_use=NS(web_search_requests=s))


def test_no_key_raises():
    with pytest.raises(AiUnavailable):
        get_client()


def test_research_with_pause_and_tool_call(session):
    client, msgs = stub(
        NS(stop_reason="pause_turn", content=[NS(type="server_tool_use", name="web_search")], usage=usage(5000, 200, 3)),
        NS(stop_reason="tool_use", content=[NS(type="text", text="klaar"),
                                            NS(type="tool_use", name="submit_research", input=RESULT)], usage=usage(8000, 1500, 2)),
    )
    rec = research.get_or_research(session, "kia", "picanto", None, client=client)
    assert isinstance(rec, IssueResearch)
    assert rec.web_searches == 5 and rec.input_tokens == 13000
    assert rec.cost_usd == pytest.approx(13000 / 1e6 * 4 + 1700 / 1e6 * 20 + 5 / 1000 * 10, rel=1e-6)
    issue = rec.result["issues"][0]
    assert issue["years"] == [2017, None] and issue["repair_cost_eur"] == [600, 900] and issue["ai"] is True
    call = msgs.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert any(t.get("type") == "web_search_20260209" for t in call["tools"])
    assert any(t.get("name") == "submit_research" and t.get("strict") for t in call["tools"])
    # second call is served from cache
    again = research.get_or_research(session, "kia", "picanto", None, client=stub()[0])
    assert again.key == rec.key


def test_research_refusal(session):
    client, _ = stub(NS(stop_reason="refusal", content=[], usage=usage()))
    with pytest.raises(AiRefused):
        research.run_research("kia", "picanto", None, client=client)


def test_nl_search_with_claude_filters_invalid_slugs():
    payload = {"explanation": "Gezinsauto", "sort": "deal", "filters": {
        "makes": ["nonsense"], "models": ["toyota/corolla", "foo/bar"], "fuels": ["hybride"], "bodies": [],
        "transmissions": [], "options": [], "price_min": None, "price_max": 20000, "km_max": None, "year_min": 2019,
        "seats_min": None, "towing_min": None, "range_min": None, "max_distance_km": None, "seller_types": [],
        "bovag_only": False, "warranty_only": False, "hide_import": False}}
    client, msgs = stub(NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(payload))], usage=usage()))
    filters, expl, sort = nl_search.with_claude("hybride corolla", client=client)
    assert filters.models == ["toyota/corolla"] and filters.makes == [] and filters.price_max == 20000
    assert sort == "deal" and expl == "Gezinsauto"
    assert msgs.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_ad_scan():
    data = {"summary": "Oké", "flags": [{"title": "Geen NAP", "severity": "medium", "detail": "x"}],
            "questions": ["NAP-rapport?"], "positives": ["Dealer"]}
    client, _ = stub(NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(data))], usage=usage(2000, 300)))
    out = ad_scan.scan(Listing(title="t", description="d", red_flags=[], first_seen_at=None), None, client=client)
    assert out["flags"][0]["title"] == "Geen NAP" and out["cost_usd"] == pytest.approx(2000 / 1e6 * 4 + 300 / 1e6 * 20)


def test_usage_pricing_unknown_model():
    u = Usage(input_tokens=1, output_tokens=1)
    assert u.cost_usd("unknown-model") is None
