"""On-demand Claude read of one advert: hidden red flags and extra questions for the seller."""

from __future__ import annotations

import json

from app.ai.client import AiRefused, Usage, get_client, request_kwargs, text_of
from app.config import get_settings
from app.models import Listing, Vehicle
from app.util import utcnow

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "flags", "questions", "positives"],
    "properties": {
        "summary": {"type": "string"},
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "severity", "detail"],
                "properties": {
                    "title": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "low", "medium", "high"]},
                    "detail": {"type": "string"},
                },
            },
        },
        "questions": {"type": "array", "items": {"type": "string"}},
        "positives": {"type": "array", "items": {"type": "string"}},
    },
}


def scan(listing: Listing, vehicle: Vehicle | None, client=None) -> dict:
    settings = get_settings()
    client = client or get_client()
    model_id = settings.claude_model
    facts = {
        "titel": listing.title,
        "prijs": listing.price_eur,
        "geschatte_marktwaarde": listing.predicted_price,
        "bouwjaar": listing.year,
        "km": listing.mileage_km,
        "brandstof": listing.fuel,
        "verkoper": listing.seller_type,
        "bovag": listing.seller_bovag,
        "garantie_maanden": listing.warranty_months,
        "dagen_online": (utcnow() - listing.first_seen_at).days if listing.first_seen_at else None,
        "regels_gevonden": [f["title"] for f in listing.red_flags or []],
    }
    if vehicle and vehicle.found:
        facts["rdw"] = {
            "eerste_toelating": str(vehicle.first_admission), "eerste_tenaamstelling_nl": str(vehicle.first_nl_registration),
            "apk_tot": str(vehicle.apk_expiry), "nap": vehicle.odometer_judgement, "open_terugroepactie": vehicle.open_recall,
            "taxi": vehicle.taxi, "import": vehicle.is_import,
        }
    response = client.beta.messages.create(
        model=model_id,
        max_tokens=4000,
        system=(
            "Je bent een kritische maar eerlijke Nederlandse occasion-expert. Lees de advertentie en de feiten. "
            "Benoem alleen signalen die echt uit de tekst of feiten volgen (geen speculatie zonder aanleiding), "
            "en formuleer concrete vragen voor de verkoper in het Nederlands. Noem ook positieve punten."
        ),
        messages=[{"role": "user", "content": (
            f"Feiten (JSON):\n{json.dumps(facts, ensure_ascii=False, default=str)}\n\n"
            f"Advertentietekst:\n<<<\n{(listing.description or '')[:8000]}\n>>>"
        )}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        **request_kwargs(model_id),
    )
    if response.stop_reason == "refusal":
        raise AiRefused("Claude weigerde dit verzoek")
    usage = Usage()
    usage.add(response.usage)
    data = json.loads(text_of(response))
    data["model"] = model_id
    data["cost_usd"] = usage.cost_usd(model_id)
    data["scanned_at"] = utcnow().isoformat()
    return data
