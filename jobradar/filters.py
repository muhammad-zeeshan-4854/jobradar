"""Filtering and relevance scoring.

A job first has to pass every hard filter (exclusions, location, salary, age).
Jobs that pass are scored 0-100 so the best matches surface first in alerts
and in the dashboard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from jobradar.models import Job

# Weights for where a keyword is found. Title matches matter most.
TITLE_WEIGHT = 30
TAG_WEIGHT = 15
DESCRIPTION_WEIGHT = 5
RECENCY_BONUS = 15
SALARY_BONUS = 10


@dataclass
class FilterConfig:
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_only: bool = False
    min_salary: int | None = None
    max_age_days: int | None = 14
    blocked_companies: list[str] = field(default_factory=list)
    min_score: float = 0.0

    @classmethod
    def from_dict(cls, data: dict | None) -> FilterConfig:
        data = data or {}
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@lru_cache(maxsize=512)
def _pattern(keyword: str) -> re.Pattern:
    # Word-boundary match that still works for terms like "c++", ".net" or "node.js".
    return re.compile(rf"(?<![\w]){re.escape(keyword.lower())}(?![\w])")


def _contains(text: str, keyword: str) -> bool:
    return bool(_pattern(keyword).search(text.lower()))


@dataclass
class FilterResult:
    passed: bool
    reason: str = ""


def check(job: Job, cfg: FilterConfig) -> FilterResult:
    haystack = " ".join([job.title, job.company, " ".join(job.tags), job.description])

    for word in cfg.exclude_keywords:
        if _contains(job.title, word) or _contains(" ".join(job.tags), word):
            return FilterResult(False, f"excluded keyword '{word}'")

    if any(c.lower() == job.company.lower() for c in cfg.blocked_companies):
        return FilterResult(False, "blocked company")

    if cfg.remote_only and not job.remote:
        return FilterResult(False, "not remote")

    if cfg.locations:
        loc = job.location.lower()
        if not any(wanted.lower() in loc for wanted in cfg.locations):
            return FilterResult(False, "location mismatch")

    if cfg.min_salary and job.salary_max and job.salary_max < cfg.min_salary:
        return FilterResult(False, "salary below minimum")

    if cfg.max_age_days is not None and job.age_days is not None and job.age_days > cfg.max_age_days:
        return FilterResult(False, "too old")

    if cfg.keywords and not any(_contains(haystack, k) for k in cfg.keywords):
        return FilterResult(False, "no keyword match")

    return FilterResult(True)


def score(job: Job, cfg: FilterConfig) -> tuple[float, list[str]]:
    """Return (score 0-100, matched keywords)."""
    if not cfg.keywords:
        base = 50.0
        matched: list[str] = []
    else:
        tags = " ".join(job.tags)
        points = 0.0
        matched = []
        for kw in cfg.keywords:
            hit = 0
            if _contains(job.title, kw):
                hit = TITLE_WEIGHT
            elif _contains(tags, kw):
                hit = TAG_WEIGHT
            elif _contains(job.description, kw):
                hit = DESCRIPTION_WEIGHT
            if hit:
                matched.append(kw)
                points += hit
        # Normalise so 2 strong title matches already count as a great fit.
        base = min(points / (TITLE_WEIGHT * 2), 1.0) * 75

    age = job.age_days
    if age is not None:
        base += RECENCY_BONUS * max(0.0, 1 - age / 7)  # fades out over a week
    if job.salary_min or job.salary_max:
        base += SALARY_BONUS
    return round(min(base, 100.0), 1), matched


def apply(jobs: list[Job], cfg: FilterConfig) -> tuple[list[Job], dict[str, int]]:
    """Filter + score a batch. Returns kept jobs (best first) and rejection counts."""
    kept: list[Job] = []
    rejected: dict[str, int] = {}
    for job in jobs:
        result = check(job, cfg)
        if not result.passed:
            rejected[result.reason] = rejected.get(result.reason, 0) + 1
            continue
        job.score, job.matched_keywords = score(job, cfg)
        if job.score < cfg.min_score:
            rejected["score below minimum"] = rejected.get("score below minimum", 0) + 1
            continue
        kept.append(job)
    kept.sort(key=lambda j: j.score, reverse=True)
    return kept, rejected
