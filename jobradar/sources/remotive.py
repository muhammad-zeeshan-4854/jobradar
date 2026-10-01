"""Remotive public API - https://remotive.com/api-documentation"""

from __future__ import annotations

from jobradar.models import Job
from jobradar.sources.base import Source, register
from jobradar.utils import parse_datetime, parse_salary, strip_html


@register
class RemotiveSource(Source):
    name = "remotive"
    display_name = "Remotive"
    homepage = "https://remotive.com"
    API_URL = "https://remotive.com/api/remote-jobs"

    def fetch(self, search_terms: list[str]) -> list[Job]:
        limit = int(self.options.get("limit", 100))
        category = self.options.get("category")
        # Remotive search is a single phrase, so query once per term and merge.
        terms = search_terms or [""]
        jobs: dict[str, Job] = {}
        for term in terms:
            params = {"limit": limit}
            if term:
                params["search"] = term
            if category:
                params["category"] = category
            payload = self._get_json(self.API_URL, params=params)
            for item in payload.get("jobs", []):
                job = self._parse(item)
                jobs[job.uid] = job
        return list(jobs.values())

    def _parse(self, item: dict) -> Job:
        smin, smax, cur = parse_salary(item.get("salary"))
        location = item.get("candidate_required_location") or "Worldwide"
        return Job(
            source=self.name,
            external_id=str(item["id"]),
            title=item.get("title", "").strip(),
            company=item.get("company_name", "").strip(),
            url=item.get("url", ""),
            location=f"Remote ({location})",
            remote=True,
            tags=[t.lower() for t in item.get("tags", [])],
            salary_min=smin,
            salary_max=smax,
            salary_currency=cur,
            description=strip_html(item.get("description")),
            posted_at=parse_datetime(item.get("publication_date")),
        )
