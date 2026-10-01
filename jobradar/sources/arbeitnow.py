"""Arbeitnow public job board API - https://www.arbeitnow.com/blog/job-board-api"""

from __future__ import annotations

from jobradar.models import Job
from jobradar.sources.base import Source, register
from jobradar.utils import looks_remote, parse_datetime, strip_html


@register
class ArbeitnowSource(Source):
    name = "arbeitnow"
    display_name = "Arbeitnow"
    homepage = "https://www.arbeitnow.com"
    API_URL = "https://www.arbeitnow.com/api/job-board-api"

    def fetch(self, search_terms: list[str]) -> list[Job]:
        max_pages = int(self.options.get("max_pages", 3))
        jobs: list[Job] = []
        url: str | None = self.API_URL
        pages = 0
        while url and pages < max_pages:
            payload = self._get_json(url)
            jobs.extend(self._parse(item) for item in payload.get("data", []))
            url = (payload.get("links") or {}).get("next")
            pages += 1
        return jobs

    def _parse(self, item: dict) -> Job:
        location = item.get("location") or ""
        remote = bool(item.get("remote")) or looks_remote(location)
        return Job(
            source=self.name,
            external_id=item["slug"],
            title=item.get("title", "").strip(),
            company=item.get("company_name", "").strip(),
            url=item.get("url", ""),
            location=f"{location} (Remote)" if remote and location else (location or "Remote"),
            remote=remote,
            tags=[t.lower() for t in (item.get("tags") or []) + (item.get("job_types") or [])],
            description=strip_html(item.get("description")),
            posted_at=parse_datetime(item.get("created_at")),
        )
