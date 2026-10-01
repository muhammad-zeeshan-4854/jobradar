"""Load config.yaml and expand ${ENV_VARS} so secrets never live in the file."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from jobradar.filters import FilterConfig

_ENV_REF = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


class ConfigError(ValueError):
    pass


def _expand(value):
    if isinstance(value, str):
        return _ENV_REF.sub(lambda m: os.getenv(m.group(1), m.group(2) or ""), value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


@dataclass
class Config:
    search_terms: list[str] = field(default_factory=list)
    sources: dict[str, dict] = field(default_factory=dict)
    filters: FilterConfig = field(default_factory=FilterConfig)
    notifiers: dict[str, dict] = field(default_factory=dict)
    database: str = "data/jobradar.db"
    max_alerts_per_run: int = 25
    interval_minutes: int = 120

    @property
    def enabled_sources(self) -> dict[str, dict]:
        return {k: v or {} for k, v in self.sources.items() if (v or {}).get("enabled", True)}

    @property
    def enabled_notifiers(self) -> dict[str, dict]:
        return {k: v or {} for k, v in self.notifiers.items() if (v or {}).get("enabled", False)}

    @classmethod
    def from_dict(cls, raw: dict) -> Config:
        raw = _expand(raw or {})
        cfg = cls(
            search_terms=raw.get("search_terms", []),
            sources=raw.get("sources") or {"remotive": {}, "remoteok": {}, "arbeitnow": {}},
            filters=FilterConfig.from_dict(raw.get("filters")),
            notifiers=raw.get("notifiers") or {},
            database=raw.get("database", "data/jobradar.db"),
            max_alerts_per_run=int(raw.get("max_alerts_per_run", 25)),
            interval_minutes=int(raw.get("interval_minutes", 120)),
        )
        if cfg.interval_minutes < 10:
            raise ConfigError("interval_minutes must be at least 10 (be polite to job sites)")
        return cfg


def load_config(path: str | Path = "config.yaml") -> Config:
    load_dotenv()
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file '{path}' not found. Run `jobradar init` to create one.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    return Config.from_dict(raw)
