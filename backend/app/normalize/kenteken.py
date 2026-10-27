"""Dutch licence plates (kenteken): normalisation, sidecode validation, formatting, extraction."""

from __future__ import annotations

import re

# Sidecodes 1–14 as group patterns (L = letter, D = digit).
SIDECODES: dict[int, tuple[str, ...]] = {
    1: ("LL", "DD", "DD"),
    2: ("DD", "DD", "LL"),
    3: ("DD", "LL", "DD"),
    4: ("LL", "DD", "LL"),
    5: ("LL", "LL", "DD"),
    6: ("DD", "LL", "LL"),
    7: ("DD", "LLL", "D"),
    8: ("D", "LLL", "DD"),
    9: ("LL", "DDD", "L"),
    10: ("L", "DDD", "LL"),
    11: ("LLL", "DD", "L"),
    12: ("L", "DD", "LLL"),
    13: ("D", "LL", "DDD"),
    14: ("DDD", "LL", "D"),
}


def _group_regex(group: str) -> str:
    return "".join("[A-Z]" if c == "L" else "[0-9]" for c in group)


_SIDECODE_RE = {
    code: re.compile("^" + "".join(f"({_group_regex(g)})" for g in groups) + "$")
    for code, groups in SIDECODES.items()
}


def normalize(value: str | None) -> str | None:
    """'ab-123-c' → 'AB123C'. Returns None when it is not a valid Dutch plate."""
    if not value:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if len(s) != 6:
        return None
    return s if sidecode(s) else None


def sidecode(plate: str) -> int | None:
    s = re.sub(r"[^A-Za-z0-9]", "", plate).upper()
    for code, rx in _SIDECODE_RE.items():
        if rx.match(s):
            return code
    return None


def format_plate(plate: str | None) -> str | None:
    """'AB123C' → 'AB-123-C'."""
    if not plate:
        return None
    s = re.sub(r"[^A-Za-z0-9]", "", plate).upper()
    code = sidecode(s)
    if not code:
        return plate
    m = _SIDECODE_RE[code].match(s)
    assert m
    return "-".join(m.groups())


# In free text we only trust plates written with dashes, or explicitly labelled as kenteken.
_DASHED = re.compile(r"(?<![A-Za-z0-9])([A-Za-z0-9]{1,3}-[A-Za-z0-9]{2,3}-[A-Za-z0-9]{1,3})(?![A-Za-z0-9])")
_LABELLED = re.compile(r"kenteken\s*[:.]?\s*([A-Za-z0-9][A-Za-z0-9\- ]{4,9}[A-Za-z0-9])", re.I)


def extract(text: str | None) -> str | None:
    if not text:
        return None
    for m in _LABELLED.finditer(text):
        plate = normalize(m.group(1).replace(" ", ""))
        if plate:
            return plate
    for m in _DASHED.finditer(text):
        candidate = m.group(1)
        if any(c.isalpha() for c in candidate) and any(c.isdigit() for c in candidate):
            plate = normalize(candidate)
            if plate:
                return plate
    return None
