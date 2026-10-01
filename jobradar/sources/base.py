"""Base class and registry for job sources.

Adding a new site means writing one class with a `fetch()` method and
decorating it with `@register`. Nothing else in the app has to change.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar

import requests

from jobradar.models import Job

log = logging.getLogger(__name__)

REGISTRY: dict[str, type[Source]] = {}


class SourceError(RuntimeError):
    """Raised when a source can't be fetched or parsed."""


class Source(ABC):
    name: ClassVar[str]
    display_name: ClassVar[str]
    homepage: ClassVar[str]

    def __init__(self, session: requests.Session, options: dict | None = None):
        self.session = session
        self.options = options or {}

    @abstractmethod
    def fetch(self, search_terms: list[str]) -> list[Job]:
        """Return raw (unfiltered) jobs from this source."""

    def _get_json(self, url: str, **kwargs):
        try:
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise SourceError(f"{self.name}: request failed: {exc}") from exc
        except ValueError as exc:
            raise SourceError(f"{self.name}: response was not valid JSON") from exc


def register(cls: type[Source]) -> type[Source]:
    REGISTRY[cls.name] = cls
    return cls


def get_source(name: str) -> type[Source]:
    try:
        return REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(REGISTRY))
        raise SourceError(f"Unknown source '{name}'. Available: {known}") from None
