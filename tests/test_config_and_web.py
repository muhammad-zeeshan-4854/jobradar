import pytest

from jobradar.config import Config, ConfigError, load_config
from jobradar.web.app import create_app


def test_env_vars_are_expanded(monkeypatch):
    monkeypatch.setenv("TOKEN", "secret")
    cfg = Config.from_dict({"notifiers": {"telegram": {"enabled": True, "bot_token": "${TOKEN}",
                                                       "chat_id": "${MISSING:-fallback}"}}})
    assert cfg.enabled_notifiers["telegram"] == {"enabled": True, "bot_token": "secret", "chat_id": "fallback"}


def test_interval_guard():
    with pytest.raises(ConfigError):
        Config.from_dict({"interval_minutes": 1})


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError, match="jobradar init"):
        load_config(tmp_path / "nope.yaml")


@pytest.fixture
def client(store, make_job):
    store.add_new([make_job(external_id="1"), make_job(external_id="2", title="Go Dev", company="B")])
    app = create_app(Config.from_dict({}), store=store)
    app.testing = True
    return app.test_client()


def test_dashboard_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Python Developer" in resp.data and b"Go Dev" in resp.data


def test_status_api(client, store):
    uid = store.query()[0][0]["uid"]
    resp = client.post(f"/api/jobs/{uid}/status", json={"status": "saved"})
    assert resp.status_code == 200 and resp.json["counts"]["saved"] == 1
    assert client.post(f"/api/jobs/{uid}/status", json={"status": "x"}).status_code == 400
    assert client.post("/api/jobs/missing/status", json={"status": "saved"}).status_code == 404


def test_json_api(client):
    data = client.get("/api/jobs?q=Go%20Dev").json
    assert data["total"] == 1 and data["jobs"][0]["title"] == "Go Dev"
    assert client.get("/health").json == {"ok": True}
