"""Motorrijtuigenbelasting (road tax) – ESTIMATE.

The exact amount depends on official per-weight-class tables (rijksdeel + provincial opcenten on a
1995-based grondslag) that we could not obtain in machine-readable form. This module therefore gives
an indication and the UI always links to the Belastingdienst calculator for the exact figure.

Basis used (2026):
- Weight basis is *massa rijklaar* from 1 July 2026 (Belastingdienst). Before that: massa ledig + 100 kg.
- Rijksdeel petrol car: €64.24/quarter at 1.000 kg, +€17.27 per 100 kg above (secondary sources citing
  art. 23 Wet MRB 1994). Below 1.000 kg we scale down linearly to a floor.
- Provincial part ≈ rijksdeel × opcenten/100 (approximation of the 1995 grondslag).
- Diesel: roughly double the petrol amount (brandstoftoeslag); fijnstoftoeslag only for diesels without a
  factory particulate filter (we assume pre-2010 diesels).
- LPG: +60% (brandstoftoeslag, approximation). Electric: 70% of the petrol rate in 2026.
  Plug-in hybrids: discount ended 1 Jan 2026 → petrol rate.
- Cars of 40+ years: exempt.

Opcenten 2026 per province: CBS 80889ned / provincial regulations (Zuid-Holland from a secondary source).
"""

from __future__ import annotations

from datetime import date

BELASTINGDIENST_URL = (
    "https://www.belastingdienst.nl/wps/wcm/connect/nl/auto-en-vervoer/content/hulpmiddel-motorrijtuigenbelasting-berekenen"
)

OPCENTEN_2026 = {
    "Groningen": 95.7,
    "Fryslân": 92.1,
    "Drenthe": 92.0,
    "Overijssel": 82.2,
    "Flevoland": 84.7,
    "Gelderland": 98.3,
    "Utrecht": 86.4,
    "Noord-Holland": 82.1,
    "Zuid-Holland": 104.4,
    "Zeeland": 84.4,
    "Noord-Brabant": 87.0,
    "Limburg": 88.5,
}

# PC2 → province (approximate; a few PC2 areas straddle a border)
_PC2_PROVINCE: dict[str, str] = {}
for _p, _codes in {
    "Noord-Holland": "10 11 12 14 15 16 17 18 19 20 21",
    "Flevoland": "13 82 83",
    "Zuid-Holland": "22 23 24 25 26 27 28 29 30 31 32 33 42",
    "Utrecht": "34 35 36 37 38 39",
    "Gelderland": "40 41 65 66 67 68 69 70 71 72 73",
    "Zeeland": "43 44 45",
    "Noord-Brabant": "46 47 48 49 50 51 52 53 54 55 56 57 58",
    "Limburg": "59 60 61 62 63 64",
    "Overijssel": "74 75 76 77 80 81",
    "Drenthe": "78 79 94",
    "Fryslân": "84 85 86 87 88 89 90 91 92",
    "Groningen": "93 95 96 97 98 99",
}.items():
    for _c in _codes.split():
        _PC2_PROVINCE[_c] = _p


def province_for_postcode(postcode: str | None) -> str | None:
    if not postcode or len(postcode) < 2 or not postcode[:2].isdigit():
        return None
    return _PC2_PROVINCE.get(postcode[:2])


def rijksdeel_petrol(weight_kg: int) -> float:
    if weight_kg >= 1000:
        steps = -(-(weight_kg - 1000) // 100)  # per started 100 kg
        return 64.24 + 17.27 * steps
    # below 1.000 kg: linear down to the lightest class
    return max(18.75, 64.24 - (1000 - weight_kg) / 100 * 9.0)


def estimate_quarter(
    weight_kg: int | None,
    fuel: str | None,
    province: str | None = None,
    first_registration: date | None = None,
    year: int = 2026,
) -> dict:
    """Return {'quarter': €, 'month': €, 'basis': ..., 'exact_url': ...} – an indication, not the exact tax."""
    if first_registration and (date.today().year - first_registration.year) >= 40:
        return {"quarter": 0.0, "month": 0.0, "basis": "Vrijgesteld (40 jaar of ouder)", "exact_url": BELASTINGDIENST_URL}
    if not weight_kg:
        return {"quarter": None, "month": None, "basis": "Gewicht onbekend", "exact_url": BELASTINGDIENST_URL}
    opc = OPCENTEN_2026.get(province or "", 90.0)
    base = rijksdeel_petrol(weight_kg)
    total_petrol = base * (1 + opc / 100)
    factor = 1.0
    note = "benzine"
    if fuel == "diesel":
        factor = 2.0
        note = "diesel (incl. brandstoftoeslag)"
        if first_registration and first_registration.year < 2010:
            factor += 0.19
            note += " + fijnstoftoeslag"
    elif fuel in ("lpg", "cng"):
        factor = 1.6
        note = "LPG/CNG (incl. brandstoftoeslag)"
    elif fuel == "elektrisch":
        factor = 0.70 if year <= 2028 else 1.0
        note = "elektrisch (70% van het tarief in 2026)"
    elif fuel == "plugin_hybride":
        note = "plug-in hybride (korting vervallen per 2026)"
    quarter = round(total_petrol * factor, 2)
    return {
        "quarter": quarter,
        "month": round(quarter / 3, 2),
        "basis": f"Schatting: {weight_kg} kg, {note}, {province or 'gemiddelde provincie'} ({opc} opcenten)",
        "exact_url": BELASTINGDIENST_URL,
    }
