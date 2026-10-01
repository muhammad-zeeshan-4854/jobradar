"""Command line interface: `jobradar <command>`."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import signal
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from jobradar import __version__
from jobradar.config import ConfigError, load_config
from jobradar.logging_setup import setup_logging
from jobradar.models import Job
from jobradar.notifiers import NOTIFIERS, NotifierError
from jobradar.pipeline import run_once
from jobradar.storage import JobStore

console = Console()
log = logging.getLogger("jobradar")
EXAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _print_result(result) -> None:
    table = Table(title="Run summary", show_header=False, box=None)
    table.add_row("Fetched", str(result.fetched))
    for name, count in sorted(result.per_source.items()):
        table.add_row(f"  {name}", str(count))
    table.add_row("Matched filters", str(result.matched))
    table.add_row("New", f"[bold green]{len(result.new_jobs)}[/]")
    table.add_row("Alerts sent", str(result.notified))
    if result.errors:
        table.add_row("Errors", f"[red]{len(result.errors)}[/]")
    console.print(table)
    for err in result.errors:
        console.print(f"  [red]•[/] {err}")
    if result.new_jobs:
        _print_jobs([j.to_dict() for j in result.new_jobs[:15]], title="New matches")


def _print_jobs(rows: list[dict], title: str) -> None:
    table = Table(title=title, header_style="bold cyan")
    table.add_column("Score", justify="right")
    table.add_column("Title", overflow="fold")
    table.add_column("Company")
    table.add_column("Location")
    table.add_column("Salary")
    table.add_column("Source", style="dim")
    for r in rows:
        job_like = Job(source="", external_id="", title="", company="", url="",
                       salary_min=r.get("salary_min"), salary_max=r.get("salary_max"),
                       salary_currency=r.get("salary_currency"))
        table.add_row(f"{r['score']:.0f}", f"[link={r['url']}]{r['title']}[/link]",
                      r["company"], r.get("location") or "", job_like.salary_display, r["source"])
    console.print(table)


# ---- commands ----------------------------------------------------------------

def cmd_init(args) -> int:
    target = Path(args.config)
    if target.exists() and not args.force:
        console.print(f"[yellow]{target} already exists[/] (use --force to overwrite)")
        return 1
    source = next((p for p in (Path("config.example.yaml"), EXAMPLE_CONFIG) if p.exists()), None)
    if source is None:
        console.print("[red]config.example.yaml not found.[/] Download it from the repository.")
        return 1
    shutil.copy(source, target)
    env = Path(".env")
    if not env.exists() and Path(".env.example").exists():
        shutil.copy(".env.example", env)
    console.print(f"[green]Created {target}[/]. Edit your keywords, then run [bold]jobradar run[/].")
    return 0


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    with _store(cfg) as store:
        result = run_once(cfg, store, send_alerts=not args.no_alerts)
    _print_result(result)
    # Non-zero exit only if *every* source failed, so CI flags real outages.
    return 2 if result.errors and not result.per_source else 0


def cmd_watch(args) -> int:
    cfg = load_config(args.config)
    interval = (args.interval or cfg.interval_minutes) * 60
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    console.print(f"[cyan]Watching every {interval // 60} min. Ctrl+C to stop.[/]")
    with _store(cfg) as store:
        try:
            while not stop["flag"]:
                try:
                    _print_result(run_once(cfg, store))
                except Exception:  # noqa: BLE001 - keep the loop alive
                    log.exception("Run failed, will retry next cycle")
                for _ in range(interval):
                    if stop["flag"]:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
    console.print("Stopped.")
    return 0


def cmd_list(args) -> int:
    cfg = load_config(args.config)
    with _store(cfg) as store:
        rows, total = store.query(search=args.search or "", status=args.status,
                                  sort=args.sort, limit=args.limit)
    _print_jobs(rows, title=f"{len(rows)} of {total} jobs")
    return 0


def cmd_stats(args) -> int:
    cfg = load_config(args.config)
    with _store(cfg) as store:
        stats = store.stats()
    console.print_json(json.dumps(stats, default=str))
    return 0


def cmd_export(args) -> int:
    cfg = load_config(args.config)
    with _store(cfg) as store:
        rows, _ = store.query(status=args.status, limit=100_000)
    out = Path(args.output)
    if args.format == "json":
        out.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    else:
        fields = ["score", "title", "company", "location", "salary_min", "salary_max",
                  "status", "source", "url", "posted_at", "first_seen"]
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    console.print(f"[green]Exported {len(rows)} jobs to {out}[/]")
    return 0


def cmd_test_notify(args) -> int:
    cfg = load_config(args.config)
    sample = Job(source="test", external_id="1", title="Test alert from JobRadar",
                 company="JobRadar", url="https://github.com", location="Remote",
                 tags=["test"], score=99)
    if not cfg.enabled_notifiers:
        console.print("[yellow]No notifiers enabled in config.[/]")
        return 1
    ok = True
    for name, options in cfg.enabled_notifiers.items():
        try:
            NOTIFIERS[name](options).send([sample])
            console.print(f"[green]✓ {name}[/]")
        except (NotifierError, KeyError) as exc:
            ok = False
            console.print(f"[red]✗ {name}: {exc}[/]")
    return 0 if ok else 1


def cmd_serve(args) -> int:
    from jobradar.web.app import create_app

    cfg = load_config(args.config)
    app = create_app(cfg)
    console.print(f"[cyan]Dashboard on http://{args.host}:{args.port}[/]")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


def cmd_demo(args) -> int:
    from jobradar.demo import seed

    cfg = load_config(args.config)
    with _store(cfg) as store:
        count = seed(store, cfg.filters)
    console.print(f"[green]Added {count} sample jobs.[/] Run [bold]jobradar serve[/] to see them.")
    return 0


class _store:
    def __init__(self, cfg):
        self.store = JobStore(cfg.database)

    def __enter__(self) -> JobStore:
        return self.store

    def __exit__(self, *exc):
        self.store.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobradar", description="Scrape, filter and get alerted about new jobs.")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config file")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"jobradar {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create config.yaml from the example")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("run", help="run one scrape cycle")
    s.add_argument("--no-alerts", action="store_true", help="store results without notifying")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("watch", help="run continuously on an interval")
    s.add_argument("--interval", type=int, help="minutes between runs (overrides config)")
    s.set_defaults(func=cmd_watch)

    s = sub.add_parser("list", help="show stored jobs")
    s.add_argument("-s", "--search")
    s.add_argument("--status", choices=["new", "saved", "applied", "hidden"])
    s.add_argument("--sort", choices=["score", "newest", "salary"], default="score")
    s.add_argument("-n", "--limit", type=int, default=20)
    s.set_defaults(func=cmd_list)

    sub.add_parser("stats", help="print database statistics").set_defaults(func=cmd_stats)

    s = sub.add_parser("export", help="export jobs to CSV or JSON")
    s.add_argument("-o", "--output", default="jobs.csv")
    s.add_argument("-f", "--format", choices=["csv", "json"], default="csv")
    s.add_argument("--status", choices=["new", "saved", "applied", "hidden"])
    s.set_defaults(func=cmd_export)

    sub.add_parser("test-notify", help="send a test alert to every enabled channel").set_defaults(func=cmd_test_notify)

    s = sub.add_parser("serve", help="start the web dashboard")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--debug", action="store_true")
    s.set_defaults(func=cmd_serve)

    sub.add_parser("demo", help="load sample jobs to try the dashboard").set_defaults(func=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    try:
        return args.func(args)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
