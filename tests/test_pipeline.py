from jobradar.config import Config
from jobradar.pipeline import run_once
from tests.conftest import FakeSession
from tests.test_sources import REMOTEOK, REMOTIVE


def make_config(**notifiers):
    return Config.from_dict({
        "search_terms": ["python"],
        "sources": {"remotive": {}, "remoteok": {}, "arbeitnow": {"enabled": False}},
        "filters": {"keywords": ["python", "go"], "max_age_days": None},
        "notifiers": notifiers,
    })


def test_full_run_stores_and_notifies_once(store):
    cfg = make_config(telegram={"enabled": True, "bot_token": "T", "chat_id": "1"})
    session = FakeSession({
        "https://remotive.com/api": REMOTIVE,
        "https://remoteok.com/api": REMOTEOK,
        "https://api.telegram.org": {"ok": True},
    })
    first = run_once(cfg, store, session=session)
    assert first.fetched == 2 and len(first.new_jobs) == 2 and first.notified == 2

    second = run_once(cfg, store, session=session)
    assert second.new_jobs == [] and second.notified == 0
    telegram_calls = [c for c in session.calls if "telegram" in c[1]]
    assert len(telegram_calls) == 1


def test_one_broken_source_does_not_stop_the_run(store):
    session = FakeSession({"https://remotive.com/api": REMOTIVE})  # remoteok -> 404
    result = run_once(make_config(), store, session=session)
    assert len(result.new_jobs) == 1
    assert any("remoteok" in e for e in result.errors)
    assert store.recent_runs(1)[0]["errors"]


def test_failed_notifier_leaves_jobs_unnotified(store):
    cfg = make_config(telegram={"enabled": True, "bot_token": "T", "chat_id": "1"})
    session = FakeSession({"https://remotive.com/api": REMOTIVE, "https://remoteok.com/api": REMOTEOK})
    result = run_once(cfg, store, session=session)  # telegram -> 404
    assert result.notified == 0
    assert any("telegram" in e for e in result.errors)
