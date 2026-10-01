"""Sample data so anyone can try the dashboard without hitting real APIs.

All companies below are fictional.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from jobradar import filters
from jobradar.models import Job
from jobradar.storage import JobStore

_ROLES = [
    ("Senior Python Developer", ["python", "django", "postgresql"]),
    ("Backend Engineer (Python/FastAPI)", ["python", "fastapi", "aws"]),
    ("Data Engineer", ["python", "airflow", "sql", "spark"]),
    ("Full Stack Developer", ["react", "node.js", "typescript"]),
    ("Junior Python Developer", ["python", "flask", "junior"]),
    ("Machine Learning Engineer", ["python", "pytorch", "mlops"]),
    ("DevOps Engineer", ["kubernetes", "terraform", "aws"]),
    ("Automation Engineer", ["python", "selenium", "ci/cd"]),
    ("Django Developer", ["python", "django", "rest"]),
    ("Platform Engineer", ["go", "kubernetes", "python"]),
    ("Web Scraping Specialist", ["python", "scrapy", "playwright"]),
    ("Frontend Engineer", ["react", "css", "typescript"]),
]
_COMPANIES = [
    "Northwind Labs", "Brightloop", "Cobalt Systems", "Lumen Health", "Fernway",
    "Quarry Analytics", "Tidewater AI", "Kestrel Pay", "Orbit Freight", "Pinecrest Software",
    "Harbor & Finch", "Saltmarsh Studio", "Juniper Cloud", "Meridian Data", "Copperleaf",
]
_LOCATIONS = [
    ("Remote (Worldwide)", True), ("Remote (Europe)", True), ("Berlin, Germany", False),
    ("London, UK (Remote)", True), ("Remote (Americas)", True), ("Amsterdam, Netherlands", False),
]
_SOURCES = ["remotive", "remoteok", "arbeitnow"]


def sample_jobs(n: int = 36, seed: int = 7) -> list[Job]:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    jobs = []
    for i in range(n):
        title, tags = rng.choice(_ROLES)
        location, remote = rng.choice(_LOCATIONS)
        has_salary = rng.random() < 0.6
        low = rng.randrange(45, 140, 5) * 1000
        jobs.append(Job(
            source=rng.choice(_SOURCES),
            external_id=f"demo-{i}",
            title=title,
            company=rng.choice(_COMPANIES),
            url=f"https://example.com/jobs/{i}",
            location=location,
            remote=remote,
            tags=tags,
            salary_min=low if has_salary else None,
            salary_max=low + rng.randrange(10, 40, 5) * 1000 if has_salary else None,
            salary_currency="USD" if has_salary else None,
            description=f"We're hiring a {title} to build and maintain production systems.",
            posted_at=now - timedelta(hours=rng.randrange(1, 24 * 5)),
        ))
    return jobs


def seed(store: JobStore, cfg: filters.FilterConfig) -> int:
    kept, _ = filters.apply(sample_jobs(), cfg)
    new = store.add_new(kept)
    rng = random.Random(3)
    for job in new[6:10]:
        store.set_status(job.uid, "saved")
    for job in new[10:13]:
        store.set_status(job.uid, "applied")
    run = store.start_run()
    store.finish_run(run, fetched=36, matched=len(kept), new_jobs=len(new),
                     notified=0, errors=[] if rng.random() > 0.5 else [])
    return len(new)
