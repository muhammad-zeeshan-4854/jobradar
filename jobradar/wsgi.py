"""Production entry point for hosting the dashboard.

    gunicorn jobradar.wsgi:app

Set JOBRADAR_DEMO=1 to load sample jobs when the database is empty, which is
useful for a public demo where the disk is reset on every deploy.
"""

from __future__ import annotations

import os
from pathlib import Path

from jobradar.config import Config, load_config
from jobradar.storage import JobStore
from jobradar.web.app import create_app


def _load_config() -> Config:
    for candidate in (os.getenv("JOBRADAR_CONFIG", "config.yaml"), "config.example.yaml"):
        if Path(candidate).exists():
            return load_config(candidate)
    return Config.from_dict({})


cfg = _load_config()

if os.getenv("JOBRADAR_DEMO") == "1":
    from jobradar.demo import seed

    _store = JobStore(cfg.database)
    if _store.stats()["total"] == 0:
        seed(_store, cfg.filters)
    _store.close()

app = create_app(cfg)
