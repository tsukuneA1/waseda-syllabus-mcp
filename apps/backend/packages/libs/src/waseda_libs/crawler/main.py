"""Crawler orchestrator.

Ties together scraper → parser → DB and exposes the CLI entry point.

Usage:
    python -m waseda_libs.crawler [options]
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv

from waseda_libs.crawler.parser import parse_syllabus
from waseda_libs.crawler.scraper import USER_AGENT, RateLimiter, fetch_all_pkeys, fetch_syllabus_html
from waseda_libs.crawler.state import CrawlState

log = logging.getLogger(__name__)

_UPSERT_SQL = """
INSERT INTO syllabuses (
    pkey, title, title_en, year, semester, credits, department,
    instructors, description, objectives, schedule, evaluation,
    textbooks, raw_html, crawled_at, updated_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s::jsonb, %s,
    %s, %s, %s, %s
)
ON CONFLICT (pkey) DO UPDATE SET
    title        = EXCLUDED.title,
    title_en     = EXCLUDED.title_en,
    year         = EXCLUDED.year,
    semester     = EXCLUDED.semester,
    credits      = EXCLUDED.credits,
    department   = EXCLUDED.department,
    instructors  = EXCLUDED.instructors,
    description  = EXCLUDED.description,
    objectives   = EXCLUDED.objectives,
    schedule     = EXCLUDED.schedule,
    evaluation   = EXCLUDED.evaluation,
    textbooks    = EXCLUDED.textbooks,
    raw_html     = EXCLUDED.raw_html,
    crawled_at   = EXCLUDED.crawled_at,
    updated_at   = NOW()
"""

_UPSERT_ERROR_SQL = """
INSERT INTO syllabuses (pkey, title, year, semester, instructors, raw_html, crawled_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (pkey) DO UPDATE SET
    raw_html   = EXCLUDED.raw_html,
    updated_at = NOW()
"""


async def _save(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    data: dict[str, Any],
    nendo: str,
) -> None:
    schedule = data.get("schedule")
    await conn.execute(
        _UPSERT_SQL,
        (
            data["pkey"],
            data["title"],
            data.get("title_en"),
            data.get("year") or int(nendo),
            data.get("semester", "unknown"),
            data.get("credits"),
            data.get("department"),
            data.get("instructors", []),
            data.get("description"),
            data.get("objectives"),
            json.dumps(schedule, ensure_ascii=False) if schedule else None,
            data.get("evaluation"),
            data.get("textbooks"),
            data.get("raw_html"),
            datetime.now(timezone.utc),
            None,
        ),
    )
    await conn.commit()


async def _save_error(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    pkey: str,
    html: str,
    nendo: str,
) -> None:
    await conn.execute(
        _UPSERT_ERROR_SQL,
        (pkey, "PARSE_ERROR", int(nendo), "unknown", [], html, datetime.now(timezone.utc)),
    )
    await conn.commit()


async def run(
    nendo: str,
    conninfo: str,
    checkpoint_path: Path,
    limit: int | None = None,
    pkeys: list[str] | None = None,
) -> None:
    state = CrawlState(checkpoint_path)

    if pkeys:
        all_pkeys = pkeys
        log.info(f"Using {len(all_pkeys)} pKeys from --pkeys")
    else:
        log.info(f"Fetching pKey list for nendo={nendo} ...")
        all_pkeys = await fetch_all_pkeys(nendo, max_pkeys=limit)
        log.info(f"Total pKeys collected: {len(all_pkeys)}")

    pending = [pk for pk in all_pkeys if not state.is_done(pk)]
    if limit is not None:
        pending = pending[:limit]

    log.info(f"Pending: {len(pending)}  |  Skipped: {len(all_pkeys) - len(pending)}")

    rate_limiter = RateLimiter(requests_per_second=1.0)
    total = len(pending)

    async with await psycopg.AsyncConnection.connect(conninfo) as db_conn:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as http_client:
            for i, pkey in enumerate(pending, 1):
                await rate_limiter.wait()
                log.info(f"[{i}/{total}] pKey={pkey}")
                try:
                    html = await fetch_syllabus_html(http_client, pkey)
                    if html is None:
                        log.warning(f"  404 – skipping")
                        state.mark_done(pkey)
                        continue

                    data = parse_syllabus(html, pkey)
                    if data is None:
                        log.warning(f"  Parse failed – saving raw HTML")
                        await _save_error(db_conn, pkey, html, nendo)
                    else:
                        await _save(db_conn, data, nendo)
                        log.info(f"  Saved: {data['title'][:50]!r}")

                    state.mark_done(pkey)

                except Exception as exc:
                    log.error(f"  Fatal: {exc}")
                    state.save()
                    raise

    state.save()
    log.info(f"Done. Processed {total} syllabuses.")


def _conninfo() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    return (
        f"postgresql://{os.environ.get('POSTGRES_USER', 'postgres')}"
        f":{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'localhost')}"
        f":{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ.get('POSTGRES_DB', 'waseda_syllabus')}"
    )


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    p = argparse.ArgumentParser(description="Waseda Syllabus Crawler")
    p.add_argument("--nendo", default="2026", help="Academic year (e.g. 2026)")
    p.add_argument("--limit", type=int, default=None, help="Max syllabuses to crawl")
    p.add_argument("--checkpoint", default="crawl_state.json", help="Checkpoint file")
    p.add_argument("--pkeys", nargs="+", default=None, help="Crawl specific pKeys only")
    args = p.parse_args()

    asyncio.run(
        run(
            nendo=args.nendo,
            conninfo=_conninfo(),
            checkpoint_path=Path(args.checkpoint),
            limit=args.limit,
            pkeys=args.pkeys,
        )
    )
