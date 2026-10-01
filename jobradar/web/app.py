"""Flask dashboard: browse matches and track your applications."""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import Flask, abort, jsonify, render_template, request

from jobradar.config import Config
from jobradar.pipeline import run_once
from jobradar.sources import REGISTRY
from jobradar.storage import STATUSES, JobStore

log = logging.getLogger(__name__)
PAGE_SIZE = 25


def _time_ago(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 3600:
        return f"{max(int(secs // 60), 1)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    days = int(secs // 86400)
    return "yesterday" if days == 1 else f"{days}d ago"


def _is_fresh(iso: str | None) -> bool:
    if not iso:
        return False
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return False
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() < 86400


def _salary(row: dict) -> str:
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if not (lo or hi):
        return ""
    sym = {"USD": "$", "EUR": "€", "GBP": "£"}.get(row.get("salary_currency") or "USD", "")
    k = lambda v: f"{sym}{v // 1000}k"  # noqa: E731
    return f"{k(lo)}–{k(hi)}" if lo and hi and lo != hi else k(lo or hi)


def create_app(cfg: Config, store: JobStore | None = None) -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    store = store or JobStore(cfg.database)
    scan_lock = threading.Lock()
    scan_state = {"running": False, "last_error": None}

    app.jinja_env.filters["ago"] = _time_ago
    app.jinja_env.filters["fresh"] = _is_fresh
    app.jinja_env.filters["salary"] = _salary
    source_names = {name: cls.display_name for name, cls in REGISTRY.items()}

    @app.template_global()
    def page_url(n: int) -> str:
        args = request.args.to_dict()
        args["page"] = str(n)
        return "?" + urlencode(args)

    def _filters_from_request() -> dict:
        remote = request.args.get("remote")
        return {
            "search": request.args.get("q", "").strip(),
            "status": request.args.get("status") or "new",
            "source": request.args.get("source") or None,
            "remote": True if remote == "1" else None,
            "sort": request.args.get("sort", "score"),
        }

    @app.get("/")
    def index():
        f = _filters_from_request()
        if f["status"] not in STATUSES:
            f["status"] = "new"
        page = max(int(request.args.get("page", 1) or 1), 1)
        rows, total = store.query(**f, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)
        return render_template(
            "index.html",
            jobs=rows,
            total=total,
            page=page,
            pages=max(math.ceil(total / PAGE_SIZE), 1),
            f=f,
            stats=store.stats(),
            statuses=STATUSES,
            source_names=source_names,
            enabled_sources=list(cfg.enabled_sources),
            scanning=scan_state["running"],
        )

    @app.get("/api/jobs")
    def api_jobs():
        f = _filters_from_request()
        if request.args.get("status") is None:
            f["status"] = None
        limit = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
        rows, total = store.query(**f, limit=limit, offset=offset)
        return jsonify({"total": total, "limit": limit, "offset": offset, "jobs": rows})

    @app.get("/api/jobs/<uid>")
    def api_job(uid: str):
        job = store.get(uid)
        if not job:
            abort(404)
        return jsonify(job)

    @app.post("/api/jobs/<uid>/status")
    def api_set_status(uid: str):
        status = (request.get_json(silent=True) or {}).get("status")
        if status not in STATUSES:
            return jsonify({"error": f"status must be one of {list(STATUSES)}"}), 400
        if not store.set_status(uid, status):
            return jsonify({"error": "job not found"}), 404
        return jsonify({"uid": uid, "status": status, "counts": store.stats()["by_status"]})

    @app.get("/api/stats")
    def api_stats():
        return jsonify(store.stats() | {"scanning": scan_state["running"]})

    @app.get("/api/runs")
    def api_runs():
        return jsonify(store.recent_runs())

    @app.post("/api/scan")
    def api_scan():
        if not scan_lock.acquire(blocking=False):
            return jsonify({"started": False, "reason": "A scan is already running"}), 409

        def worker():
            scan_state["running"] = True
            try:
                worker_store = JobStore(cfg.database)
                try:
                    run_once(cfg, worker_store)
                finally:
                    worker_store.close()
                scan_state["last_error"] = None
            except Exception as exc:  # noqa: BLE001
                log.exception("Scan failed")
                scan_state["last_error"] = str(exc)
            finally:
                scan_state["running"] = False
                scan_lock.release()

        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"started": True}), 202

    @app.get("/health")
    def health():
        return {"ok": True}

    return app
