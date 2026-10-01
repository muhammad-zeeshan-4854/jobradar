from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from jobradar.models import Job
from jobradar.storage import JobStore


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Maps URL prefixes to canned JSON so tests never touch the network."""

    def __init__(self, routes: dict[str, object] | None = None):
        self.routes = routes or {}
        self.calls: list[tuple[str, str, dict]] = []

    def _match(self, url):
        for prefix, payload in self.routes.items():
            if url.startswith(prefix):
                if isinstance(payload, Exception):
                    raise payload
                if isinstance(payload, FakeResponse):
                    return payload
                return FakeResponse(payload)
        return FakeResponse({}, status=404)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._match(url)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._match(url)


@pytest.fixture
def make_job():
    def _make(**overrides) -> Job:
        defaults = dict(
            source="test",
            external_id="1",
            title="Python Developer",
            company="Acme",
            url="https://example.com/1",
            location="Remote (Worldwide)",
            remote=True,
            tags=["python", "django"],
            description="Build APIs with Python.",
            posted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        defaults.update(overrides)
        return Job(**defaults)

    return _make


@pytest.fixture
def store():
    s = JobStore(":memory:")
    yield s
    s.close()
