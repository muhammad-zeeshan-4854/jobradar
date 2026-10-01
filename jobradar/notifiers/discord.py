"""Discord alerts via an incoming webhook (Server settings > Integrations)."""

from __future__ import annotations

import requests

from jobradar.models import Job
from jobradar.notifiers.base import Notifier, NotifierError, job_line

EMBEDS_PER_MESSAGE = 10


class DiscordNotifier(Notifier):
    name = "discord"

    def required_options(self) -> list[str]:
        return ["webhook_url"]

    def send(self, jobs: list[Job]) -> None:
        self.validate()
        session = self.session or requests
        for i in range(0, len(jobs), EMBEDS_PER_MESSAGE):
            chunk = jobs[i : i + EMBEDS_PER_MESSAGE]
            payload = {
                "username": "JobRadar",
                "content": f"**{len(jobs)} new job matches**" if i == 0 else None,
                "embeds": [self._embed(j) for j in chunk],
            }
            try:
                session.post(self.options["webhook_url"], json=payload).raise_for_status()
            except requests.RequestException as exc:
                raise NotifierError(f"discord: {exc}") from exc

    @staticmethod
    def _embed(job: Job) -> dict:
        embed = {
            "title": job.title[:256],
            "url": job.url,
            "description": job_line(job)[:4096],
            "color": 0x1F6F8B,
            "footer": {"text": f"{job.source} · score {job.score:.0f}"},
        }
        if job.tags:
            embed["fields"] = [{"name": "Tags", "value": ", ".join(job.tags[:8])[:1024]}]
        return embed
