"""SQLite persistence: seen jobs, application status and run history."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from jobradar.models import Job

STATUSES = ("new", "saved", "applied", "hidden")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid              TEXT PRIMARY KEY,
    fingerprint      TEXT NOT NULL,
    source           TEXT NOT NULL,
    external_id      TEXT NOT NULL,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    url              TEXT NOT NULL,
    location         TEXT,
    remote           INTEGER NOT NULL DEFAULT 0,
    tags             TEXT NOT NULL DEFAULT '[]',
    salary_min       INTEGER,
    salary_max       INTEGER,
    salary_currency  TEXT,
    description      TEXT,
    posted_at        TEXT,
    score            REAL NOT NULL DEFAULT 0,
    matched_keywords TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'new',
    notified         INTEGER NOT NULL DEFAULT 0,
    first_seen       TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    fetched     INTEGER NOT NULL DEFAULT 0,
    matched     INTEGER NOT NULL DEFAULT 0,
    new_jobs    INTEGER NOT NULL DEFAULT 0,
    notified    INTEGER NOT NULL DEFAULT 0,
    errors      TEXT NOT NULL DEFAULT '[]'
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ---- writing -----------------------------------------------------------

    def add_new(self, jobs: list[Job]) -> list[Job]:
        """Insert jobs we haven't seen before. Returns only the new ones.

        Duplicates are detected both by uid (same listing) and by fingerprint
        (same role + company cross-posted on another site).
        """
        new: list[Job] = []
        with self._tx() as conn:
            for job in jobs:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO jobs
                    (uid, fingerprint, source, external_id, title, company, url, location,
                     remote, tags, salary_min, salary_max, salary_currency, description,
                     posted_at, score, matched_keywords, first_seen)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job.uid, job.fingerprint, job.source, job.external_id, job.title,
                        job.company, job.url, job.location, int(job.remote), json.dumps(job.tags),
                        job.salary_min, job.salary_max, job.salary_currency, job.description,
                        job.posted_at.isoformat() if job.posted_at else None, job.score,
                        json.dumps(job.matched_keywords), _now(),
                    ),
                )
                if cur.rowcount:
                    new.append(job)
        return new

    def mark_notified(self, uids: list[str]) -> None:
        if not uids:
            return
        with self._tx() as conn:
            conn.executemany("UPDATE jobs SET notified = 1 WHERE uid = ?", [(u,) for u in uids])

    def set_status(self, uid: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self._tx() as conn:
            cur = conn.execute("UPDATE jobs SET status = ? WHERE uid = ?", (status, uid))
        return cur.rowcount > 0

    def start_run(self) -> int:
        with self._tx() as conn:
            cur = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (_now(),))
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, *, fetched: int, matched: int, new_jobs: int,
                   notified: int, errors: list[str]) -> None:
        with self._tx() as conn:
            conn.execute(
                """UPDATE runs SET finished_at=?, fetched=?, matched=?, new_jobs=?,
                   notified=?, errors=? WHERE id=?""",
                (_now(), fetched, matched, new_jobs, notified, json.dumps(errors), run_id),
            )

    # ---- reading -----------------------------------------------------------

    def query(self, *, search: str = "", status: str | None = None, source: str | None = None,
              remote: bool | None = None, min_score: float = 0, sort: str = "score",
              limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        where, params = ["score >= ?"], [min_score]
        if search:
            where.append("(title LIKE ? OR company LIKE ? OR tags LIKE ? OR location LIKE ?)")
            params += [f"%{search}%"] * 4
        if status:
            where.append("status = ?")
            params.append(status)
        else:
            where.append("status != 'hidden'")
        if source:
            where.append("source = ?")
            params.append(source)
        if remote is not None:
            where.append("remote = ?")
            params.append(int(remote))

        order = {
            "score": "score DESC, first_seen DESC",
            "newest": "COALESCE(posted_at, first_seen) DESC",
            "salary": "COALESCE(salary_max, salary_min, 0) DESC",
        }.get(sort, "score DESC")
        clause = " AND ".join(where)
        total = self._conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {clause}", params).fetchone()[0]
        rows = self._conn.execute(
            f"SELECT * FROM jobs WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        return [self._row(r) for r in rows], total

    def get(self, uid: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE uid = ?", (uid,)).fetchone()
        return self._row(row) if row else None

    def stats(self) -> dict:
        c = self._conn
        by_status = dict(c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
        by_source = dict(c.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source").fetchall())
        top_tags: dict[str, int] = {}
        for (tags,) in c.execute("SELECT tags FROM jobs WHERE status != 'hidden'"):
            for tag in json.loads(tags):
                top_tags[tag] = top_tags.get(tag, 0) + 1
        last_run = c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        week = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE first_seen >= datetime('now', '-7 days')"
        ).fetchone()[0]
        return {
            "total": sum(by_status.values()),
            "by_status": {s: by_status.get(s, 0) for s in STATUSES},
            "by_source": by_source,
            "new_this_week": week,
            "top_tags": sorted(top_tags.items(), key=lambda kv: kv[1], reverse=True)[:12],
            "last_run": dict(last_run) if last_run else None,
        }

    def recent_runs(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) | {"errors": json.loads(r["errors"])} for r in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["tags"] = json.loads(data["tags"])
        data["matched_keywords"] = json.loads(data["matched_keywords"])
        data["remote"] = bool(data["remote"])
        return data
