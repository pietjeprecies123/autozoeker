from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime
from itertools import pairwise


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite stores datetimes without tz)."""
    return datetime.now(UTC).replace(tzinfo=None)


def today() -> date:
    return utcnow().date()


def age_in_months(first_registration: date | None, year: int | None, ref: date | None = None) -> int | None:
    ref = ref or today()
    if first_registration:
        return max(0, (ref.year - first_registration.year) * 12 + ref.month - first_registration.month)
    if year:
        return max(0, (ref.year - year) * 12 + ref.month - 7)
    return None


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value


def parse_int(value) -> int | None:
    """Parse '12.345 km', '€ 15.950,-', 15950.0 → int. Returns None if no digits."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    s = str(value).strip()
    # a plain decimal number ("15950.00", "435.0"); three digits after a dot are thousands ("15.950")
    if re.fullmatch(r"\d+\.\d{1,2}", s):
        return int(round(float(s)))
    # strip decimal part written as ',-' or ',00'
    s = re.sub(r",(-|\d{1,2})(?!\d)", "", s)
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


def parse_date(value) -> date | None:
    """Accepts 20190612, '2019-06-12', '2019-06-12T00:00:00.000', '06-2019', '06/2019', '2019'."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if re.fullmatch(r"\d{8}", s):
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})[-/](\d{4})", s)
    if m:
        month = int(m[1])
        if 1 <= month <= 12:
            return date(int(m[2]), month, 1)
        return None
    m = re.fullmatch(r"(\d{4})", s)
    if m:
        return date(int(m[1]), 7, 1)
    return None


def euro(value: int | float | None) -> str:
    if value is None:
        return "–"
    return "€ " + f"{int(round(value)):,}".replace(",", ".")


def km(value: int | float | None) -> str:
    if value is None:
        return "–"
    return f"{int(round(value)):,}".replace(",", ".") + " km"


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


_NEGATION = re.compile(
    r"\b(?:geen|zonder|niet voor|niet|nooit)\s+(?:(?:enkele|echte|grote|zichtbare)\s+)?"
    r"(?:[\w-]+\s*(?:,|of|en|noch)\s+)?$"
)


def negated(text: str, start: int) -> bool:
    """True when the word at `start` is negated: 'geen schade', 'niet voor export', 'geen diesel of lpg'."""
    return bool(_NEGATION.search(text[max(0, start - 40):start]))


def price_drops(prices) -> int:
    """Number of reductions in a chronological price history (PriceHistory rows or plain prices)."""
    values = [getattr(p, "price_eur", p) for p in prices or []]
    return sum(1 for a, b in pairwise(values) if a and b and b < a)
