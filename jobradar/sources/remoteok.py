"""RemoteOK public API - https://remoteok.com/api

RemoteOK asks API users to link back to the original listing, which JobRadar
does by always using the listing URL in alerts and the dashboard.
"""

from __future__ import annotations

from jobradar.models import Job
from jobradar.sources.base import Source, register
from jobradar.utils import parse_datetime, strip_html


@register
class RemoteOKSource(Source):
    name = "remoteok"
    display_name = "RemoteOK"
    homepage = "https://remoteok.com"
    API_URL = "https://remoteok.com/api"

    def fetch(self, search_terms: list[str]) -> list[Job]:
        payload = self._get_json(self.API_URL)
        # The first element is a legal notice, not a job.
        items = [i for i in payload if isinstance(i, dict) and i.get("id") and i.get("position")]
        return [self._parse(i) for i in items]

    def _parse(self, item: dict) -> Job:
        smin = item.get("salary_min") or None
        smax = item.get("salary_max") or None
        return Job(
            source=self.name,
            external_id=str(item["id"]),
            title=item.get("position", "").strip(),
            company=item.get("company", "").strip(),
            url=item.get("url") or item.get("apply_url", ""),
            location=item.get("location") or "Remote",
            remote=True,
            tags=[t.lower() for t in item.get("tags", [])],
            salary_min=int(smin) if smin else None,
            salary_max=int(smax) if smax else None,
            salary_currency="USD" if (smin or smax) else None,
            description=strip_html(item.get("description")),
            posted_at=parse_datetime(item.get("epoch") or item.get("date")),
        )
