"""Background jobs: crawl cycle (sources → ingest → score → alerts), nightly retrain, daily digest."""

from __future__ import annotations

import logging
import random
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.db import session_scope
from app.util import utcnow

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()
_last: dict[str, str] = {}


def crawl_cycle() -> dict:
    """One full cycle. Safe to call manually; runs are serialized by a lock."""
    from app.alerts.engine import process
    from app.analysis import refresh
    from app.demo.seed import demo_tick
    from app.ingest.pipeline import IngestResult, blocked_until, confirm_stale, crawl, queries_for_crawl
    from app.sources.registry import enabled_adapters

    if not _lock.acquire(blocking=False):
        return {"skipped": "already running"}
    try:
        settings = get_settings()
        total = IngestResult()
        with session_scope() as session:
            if settings.demo_mode or "demo" in settings.source_list:
                total.merge(demo_tick(session))
            adapters = enabled_adapters()
            if adapters:
                queries = queries_for_crawl(session)
                for adapter in adapters:
                    if blocked_until(session, adapter.name):
                        continue
                    blocked = False
                    for q in queries:
                        q.max_pages = settings.crawl_max_pages
                        r = crawl(session, adapter, q)
                        total.merge(r)
                        if r.blocked:
                            blocked = True
                            break
                    if not blocked:
                        total.merge(confirm_stale(session, adapter))
            refresh(session, total.touched)
            alerts = process(session, total)
        result = {"new": len(total.new), "price_changed": len(total.price_changed), "back": len(total.back),
                  "removed": len(total.removed), "alerts": len(alerts), "errors": len(total.errors)}
        _last["crawl"] = f"{utcnow().isoformat(timespec='seconds')} {result}"
        log.info("crawl cycle: %s", result)
        return result
    finally:
        _lock.release()


def nightly() -> None:
    from app.analysis import refresh

    with session_scope() as session:
        refresh(session, retrain=True)
    _last["nightly"] = utcnow().isoformat(timespec="seconds")


def digest() -> None:
    from app.alerts.engine import send_digests

    with session_scope() as session:
        n = send_digests(session)
    _last["digest"] = f"{utcnow().isoformat(timespec='seconds')} sent={n}"


def start() -> None:
    global _scheduler
    settings = get_settings()
    if _scheduler is not None or not settings.scheduler_enabled:
        return
    _scheduler = BackgroundScheduler(timezone="Europe/Amsterdam")
    _scheduler.add_job(crawl_cycle, IntervalTrigger(minutes=settings.crawl_interval_min, jitter=120),
                       id="crawl", max_instances=1, coalesce=True)
    _scheduler.add_job(nightly, CronTrigger(hour=3, minute=random.randint(5, 50)), id="nightly", max_instances=1)
    _scheduler.add_job(digest, CronTrigger(hour=settings.digest_hour, minute=0), id="digest", max_instances=1)
    _scheduler.start()
    log.info("scheduler started (crawl every %s min)", settings.crawl_interval_min)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def scheduler_info() -> dict:
    jobs = []
    if _scheduler is not None:
        for job in _scheduler.get_jobs():
            jobs.append({"id": job.id, "next_run": job.next_run_time.isoformat() if job.next_run_time else None})
    return {"running": _scheduler is not None, "jobs": jobs, "last": dict(_last)}
