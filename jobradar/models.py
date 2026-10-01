"""Core data model shared by every source, filter, store and notifier."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

_NON_WORD = re.compile(r"[^a-z0-9]+")
_COMPANY_SUFFIXES = re.compile(r"\b(inc|llc|ltd|gmbh|corp|co|limited|pvt)\b\.?")


def _normalize(text: str) -> str:
    text = text.lower()
    text = _COMPANY_SUFFIXES.sub("", text)
    return _NON_WORD.sub(" ", text).strip()


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    url: str
    location: str = ""
    remote: bool = False
    tags: list[str] = field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Stable id for one listing on one source."""
        raw = f"{self.source}:{self.external_id}".encode()
        return hashlib.sha256(raw).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        """Same role at the same company, regardless of which site posted it.

        Used to drop cross-posted duplicates (a job on both Remotive and RemoteOK).
        """
        raw = f"{_normalize(self.title)}|{_normalize(self.company)}".encode()
        return hashlib.sha1(raw).hexdigest()[:16]

    @property
    def age_days(self) -> float | None:
        if not self.posted_at:
            return None
        delta = datetime.now(timezone.utc) - self.posted_at
        return max(delta.total_seconds() / 86400, 0.0)

    @property
    def salary_display(self) -> str:
        if not (self.salary_min or self.salary_max):
            return ""
        cur = self.salary_currency or "USD"
        symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(cur, f"{cur} ")

        def fmt(v: int) -> str:
            return f"{symbol}{v // 1000}k" if v >= 1000 else f"{symbol}{v}"

        if self.salary_min and self.salary_max and self.salary_min != self.salary_max:
            return f"{fmt(self.salary_min)}–{fmt(self.salary_max)}"
        return fmt(self.salary_min or self.salary_max)  # type: ignore[arg-type]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["uid"] = self.uid
        data["fingerprint"] = self.fingerprint
        data["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        data["salary_display"] = self.salary_display
        return data
