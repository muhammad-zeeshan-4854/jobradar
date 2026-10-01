"""A shared requests session with retries, backoff and a polite user agent."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobradar import __version__

USER_AGENT = f"JobRadar/{__version__} (+https://github.com/muhammad-zeeshan-4854/jobradar)"
DEFAULT_TIMEOUT = 20


class TimeoutSession(requests.Session):
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        super().__init__()
        self._timeout = timeout

    def request(self, *args, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", self._timeout)
        return super().request(*args, **kwargs)


def build_session(retries: int = 3, backoff: float = 1.5, timeout: int = DEFAULT_TIMEOUT) -> requests.Session:
    session = TimeoutSession(timeout=timeout)
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session
