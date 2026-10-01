"""Small parsing helpers used by the source adapters."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SALARY_NUM = re.compile(r"(\d+(?:[.,]\d+)?)\s*(k)?", re.IGNORECASE)
_CURRENCY = {"$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR", "£": "GBP", "gbp": "GBP"}


def strip_html(text: str | None, max_len: int = 600) -> str:
    """Turn an HTML job description into a short plain-text snippet."""
    if not text:
        return ""
    plain = _WS.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()
    if len(plain) <= max_len:
        return plain
    return plain[:max_len].rsplit(" ", 1)[0] + "…"


def parse_salary(text: str | None) -> tuple[int | None, int | None, str | None]:
    """Parse free-text salary like '$80k - $100k' or '60,000-75,000 EUR'.

    Returns (min, max, currency). Values that look hourly (< 1000) are ignored
    because they can't be compared with annual figures.
    """
    if not text:
        return None, None, None
    lowered = text.lower()
    currency = next((code for sym, code in _CURRENCY.items() if sym in lowered), None)

    values: list[int] = []
    for number, kilo in _SALARY_NUM.findall(lowered.replace(",", "")):
        value = float(number)
        if kilo:
            value *= 1000
        if value >= 1000:
            values.append(int(value))
    if not values:
        return None, None, currency
    return min(values), max(values), currency


def parse_datetime(value) -> datetime | None:
    """Accept ISO strings, unix epochs (int/str) or None. Always returns UTC."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def looks_remote(location: str) -> bool:
    loc = location.lower()
    return any(word in loc for word in ("remote", "anywhere", "worldwide", "global"))
