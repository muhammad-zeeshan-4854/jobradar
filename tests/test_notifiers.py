import pytest

from jobradar.notifiers import NOTIFIERS, NotifierError
from jobradar.notifiers.email import EmailNotifier
from jobradar.notifiers.telegram import MAX_MESSAGE, TelegramNotifier
from tests.conftest import FakeSession


def test_missing_settings_raise(make_job):
    with pytest.raises(NotifierError, match="bot_token"):
        TelegramNotifier({}).send([make_job()])


def test_telegram_escapes_html_and_splits_long_batches(make_job):
    session = FakeSession({"https://api.telegram.org": {"ok": True}})
    jobs = [make_job(external_id=str(i), title=f"Dev <{i}> & co " + "x" * 150) for i in range(60)]
    TelegramNotifier({"bot_token": "T", "chat_id": "1"}, session=session).send(jobs)
    texts = [kw["json"]["text"] for _, _, kw in session.calls]
    assert len(texts) > 1
    assert all(len(t) <= MAX_MESSAGE for t in texts)
    assert "&lt;0&gt; &amp; co" in texts[0]


def test_discord_batches_ten_embeds(make_job):
    session = FakeSession({"https://discord.test": {}})
    jobs = [make_job(external_id=str(i)) for i in range(23)]
    NOTIFIERS["discord"]({"webhook_url": "https://discord.test/hook"}, session=session).send(jobs)
    assert [len(kw["json"]["embeds"]) for _, _, kw in session.calls] == [10, 10, 3]


def test_email_message_has_text_and_html(make_job):
    n = EmailNotifier({"smtp_host": "x", "username": "me@x.com", "password": "p", "to": ["a@x.com", "b@x.com"]})
    msg = n.build_message([make_job(title="Python <Dev>")])
    assert msg["To"] == "a@x.com, b@x.com"
    html_part = msg.get_body(preferencelist=("html",)).get_content()
    assert "Python &lt;Dev&gt;" in html_part
