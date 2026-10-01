"""Telegram bot alerts. Create a bot with @BotFather, then get your chat id
by messaging the bot and opening https://api.telegram.org/bot<TOKEN>/getUpdates
"""

from __future__ import annotations

import html

import requests

from jobradar.models import Job
from jobradar.notifiers.base import Notifier, NotifierError, job_line

MAX_MESSAGE = 4000  # Telegram's hard limit is 4096 characters


class TelegramNotifier(Notifier):
    name = "telegram"

    def required_options(self) -> list[str]:
        return ["bot_token", "chat_id"]

    def send(self, jobs: list[Job]) -> None:
        self.validate()
        for message in self._build_messages(jobs):
            self._post(message)

    def _build_messages(self, jobs: list[Job]) -> list[str]:
        header = f"<b>🛰 JobRadar: {len(jobs)} new match{'es' if len(jobs) != 1 else ''}</b>\n\n"
        blocks = []
        for job in jobs:
            title = html.escape(job.title)
            meta = html.escape(job_line(job))
            block = f'<b><a href="{html.escape(job.url, quote=True)}">{title}</a></b>\n{meta}\n'
            if job.matched_keywords:
                block += f"<i>matched: {html.escape(', '.join(job.matched_keywords))}</i> · score {job.score:.0f}\n"
            blocks.append(block + "\n")

        messages, current = [], header
        for block in blocks:
            if len(current) + len(block) > MAX_MESSAGE:
                messages.append(current)
                current = ""
            current += block
        if current.strip():
            messages.append(current)
        return messages

    def _post(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.options['bot_token']}/sendMessage"
        session = self.session or requests
        try:
            resp = session.post(url, json={
                "chat_id": self.options["chat_id"],
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"telegram: {exc}") from exc
