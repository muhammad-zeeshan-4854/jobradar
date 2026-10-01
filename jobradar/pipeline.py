"""One scrape cycle: fetch -> filter/score -> dedupe/store -> notify."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests

from jobradar import filters
from jobradar.config import Config
from jobradar.http import build_session
from jobradar.models import Job
from jobradar.notifiers import NOTIFIERS, NotifierError
from jobradar.sources import SourceError, get_source
from jobradar.storage import JobStore

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    fetched: int = 0
    matched: int = 0
    new_jobs: list[Job] = field(default_factory=list)
    notified: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def fetch_all(cfg: Config, session: requests.Session, result: RunResult) -> list[Job]:
    """Fetch every enabled source in parallel. One broken site never stops the run."""
    jobs: list[Job] = []
    sources = []
    for name, options in cfg.enabled_sources.items():
        try:
            sources.append(get_source(name)(session, options))
        except SourceError as exc:
            result.errors.append(str(exc))

    with ThreadPoolExecutor(max_workers=max(len(sources), 1)) as pool:
        futures = {pool.submit(s.fetch, cfg.search_terms): s for s in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                batch = future.result()
            except Exception as exc:  # noqa: BLE001 - isolate any source failure
                msg = f"{source.name}: {exc}"
                log.warning("Source failed - %s", msg)
                result.errors.append(msg)
                continue
            result.per_source[source.name] = len(batch)
            log.info("Fetched %d jobs from %s", len(batch), source.display_name)
            jobs.extend(batch)
    return jobs


def notify(cfg: Config, jobs: list[Job], session: requests.Session, result: RunResult) -> list[str]:
    """Send alerts to every enabled channel. Returns uids that reached at least one."""
    if not jobs or not cfg.enabled_notifiers:
        return []
    delivered = False
    for name, options in cfg.enabled_notifiers.items():
        notifier_cls = NOTIFIERS.get(name)
        if not notifier_cls:
            result.errors.append(f"Unknown notifier '{name}'")
            continue
        try:
            notifier_cls(options, session=session).send(jobs)
            log.info("Sent %d alerts via %s", len(jobs), name)
            delivered = True
        except NotifierError as exc:
            log.error("Notifier failed - %s", exc)
            result.errors.append(str(exc))
    return [j.uid for j in jobs] if delivered else []


def run_once(cfg: Config, store: JobStore, session: requests.Session | None = None,
             send_alerts: bool = True) -> RunResult:
    session = session or build_session()
    result = RunResult()
    run_id = store.start_run()
    try:
        raw = fetch_all(cfg, session, result)
        result.fetched = len(raw)

        kept, result.rejected = filters.apply(raw, cfg.filters)
        result.matched = len(kept)

        result.new_jobs = store.add_new(kept)
        log.info("%d matched, %d new", result.matched, len(result.new_jobs))

        if send_alerts:
            to_send = result.new_jobs[: cfg.max_alerts_per_run]
            sent = notify(cfg, to_send, session, result)
            store.mark_notified(sent)
            result.notified = len(sent)
    finally:
        store.finish_run(
            run_id,
            fetched=result.fetched,
            matched=result.matched,
            new_jobs=len(result.new_jobs),
            notified=result.notified,
            errors=result.errors,
        )
    return result
