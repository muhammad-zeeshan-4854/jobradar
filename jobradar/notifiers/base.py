from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from jobradar.models import Job


class NotifierError(RuntimeError):
    pass


class Notifier(ABC):
    name: ClassVar[str]

    def __init__(self, options: dict, session=None):
        self.options = options
        self.session = session

    @abstractmethod
    def send(self, jobs: list[Job]) -> None:
        """Deliver a batch of new jobs. Raise NotifierError on failure."""

    def validate(self) -> None:
        missing = [k for k in self.required_options() if not self.options.get(k)]
        if missing:
            raise NotifierError(f"{self.name}: missing settings {', '.join(missing)}")

    def required_options(self) -> list[str]:
        return []


def job_line(job: Job) -> str:
    parts = [job.company, job.location]
    if job.salary_display:
        parts.append(job.salary_display)
    return " | ".join(p for p in parts if p)
