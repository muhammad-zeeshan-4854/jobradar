"""HTML email digest over SMTP. For Gmail use an App Password, not your login."""

from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage

from jobradar.models import Job
from jobradar.notifiers.base import Notifier, NotifierError


class EmailNotifier(Notifier):
    name = "email"

    def required_options(self) -> list[str]:
        return ["smtp_host", "username", "password", "to"]

    def send(self, jobs: list[Job]) -> None:
        self.validate()
        msg = self.build_message(jobs)
        host = self.options["smtp_host"]
        port = int(self.options.get("smtp_port", 587))
        context = ssl.create_default_context()
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
                    smtp.login(self.options["username"], self.options["password"])
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    smtp.starttls(context=context)
                    smtp.login(self.options["username"], self.options["password"])
                    smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotifierError(f"email: {exc}") from exc

    def build_message(self, jobs: list[Job]) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"JobRadar: {len(jobs)} new job match{'es' if len(jobs) != 1 else ''}"
        msg["From"] = self.options.get("from") or self.options["username"]
        to = self.options["to"]
        msg["To"] = ", ".join(to) if isinstance(to, list) else to
        msg.set_content("\n\n".join(f"{j.title} - {j.company}\n{j.url}" for j in jobs))
        msg.add_alternative(self._html(jobs), subtype="html")
        return msg

    @staticmethod
    def _html(jobs: list[Job]) -> str:
        rows = []
        for j in jobs:
            meta = " &nbsp;|&nbsp; ".join(
                html.escape(p) for p in (j.company, j.location, j.salary_display) if p
            )
            tags = "".join(
                f'<span style="display:inline-block;background:#E6EFF2;color:#1F4E5F;'
                f'border-radius:4px;padding:2px 6px;margin:2px 4px 0 0;font-size:12px">{html.escape(t)}</span>'
                for t in j.tags[:6]
            )
            rows.append(
                f'<tr><td style="padding:16px 0;border-bottom:1px solid #D9DED8">'
                f'<a href="{html.escape(j.url, quote=True)}" style="font-size:16px;font-weight:600;'
                f'color:#17202B;text-decoration:none">{html.escape(j.title)}</a>'
                f'<div style="color:#5B6670;font-size:14px;margin-top:4px">{meta}</div>'
                f'<div style="margin-top:6px">{tags}</div></td>'
                f'<td style="padding:16px 0 16px 16px;border-bottom:1px solid #D9DED8;'
                f'text-align:right;color:#1F6F8B;font-weight:700;font-size:18px">{j.score:.0f}</td></tr>'
            )
        return (
            '<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto;color:#17202B">'
            f'<h2 style="margin:0 0 4px">{len(jobs)} new matches</h2>'
            '<p style="color:#5B6670;margin:0 0 12px">Sorted by match score (0-100).</p>'
            f'<table width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'
            '<p style="color:#8A939B;font-size:12px;margin-top:20px">Sent by JobRadar</p></div>'
        )
