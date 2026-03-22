"""Waseda syllabus crawler.

Usage:
    uv run --package waseda-libs python -m waseda_libs.crawler.scraper [options]

Options:
    --nendo YEAR        Academic year to crawl (default: 2026)
    --limit N           Stop after N syllabuses (useful for testing)
    --checkpoint PATH   Checkpoint file for resuming (default: crawl_state.json)
"""

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psycopg
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from waseda_libs.crawler.parser import parse_syllabus
from waseda_libs.crawler.state import CrawlState

log = logging.getLogger(__name__)

BASE_URL = "https://www.wsl.waseda.jp/syllabus"
USER_AGENT = "WasedaSyllabusMCP/1.0 (research purpose)"

UPSERT_SQL = """
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

UPSERT_ERROR_SQL = """
INSERT INTO syllabuses (pkey, title, year, semester, instructors, raw_html, crawled_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (pkey) DO UPDATE SET
    raw_html   = EXCLUDED.raw_html,
    updated_at = NOW()
"""


# ---------------------------------------------------------------------------
# pKey collection via Playwright
# ---------------------------------------------------------------------------


async def fetch_all_pkeys(nendo: str) -> list[str]:
    """Collect all pKeys from JAA103.php using Playwright."""
    url = f"{BASE_URL}/JAA103.php?pLng=jp&nendo={nendo}"
    pkeys: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        try:
            log.info(f"Opening {url}")
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            page_num = 1
            while True:
                links = await page.query_selector_all("a[href*='JAA104.php']")
                for link in links:
                    href = await link.get_attribute("href")
                    if href and "pKey=" in href:
                        pkey = href.split("pKey=")[1].split("&")[0]
                        if len(pkey) == 28:
                            pkeys.append(pkey)

                log.info(
                    f"  Page {page_num}: {len(links)} links collected "
                    f"(running total: {len(pkeys)})"
                )

                # Try several selectors for the "next page" control
                next_btn = None
                for selector in [
                    "input[value*='次の']",
                    "input[value*='Next']",
                    "a:has-text('次のページ')",
                    "a:has-text('次へ')",
                    ".next a",
                    "td.next a",
                ]:
                    next_btn = await page.query_selector(selector)
                    if next_btn:
                        break

                if not next_btn:
                    log.info("No next-page button found — collection complete.")
                    break

                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                page_num += 1

        finally:
            await browser.close()

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for pk in pkeys:
        if pk not in seen:
            seen.add(pk)
            unique.append(pk)

    return unique


# ---------------------------------------------------------------------------
# Syllabus detail fetching via httpx
# ---------------------------------------------------------------------------


class RateLimiter:
    """Ensures a minimum interval between requests."""

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self.interval = 1.0 / requests_per_second
        self._last: float = 0.0

    async def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self._last = time.monotonic()


@retry(
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _fetch_html(client: httpx.AsyncClient, pkey: str) -> str | None:
    url = f"{BASE_URL}/JAA104.php?pKey={pkey}&pLng=jp"
    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise


# ---------------------------------------------------------------------------
# Database UPSERT
# ---------------------------------------------------------------------------


def _to_json_str(value: Any) -> str | None:
    """Convert a Python object to a JSON string for JSONB columns."""
    if value is None:
        return None
    import json
    return json.dumps(value, ensure_ascii=False)


async def save_to_db(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    data: dict[str, Any],
    nendo: str,
) -> None:
    now = datetime.now(timezone.utc)
    await conn.execute(
        UPSERT_SQL,
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
            _to_json_str(data.get("schedule")),
            data.get("evaluation"),
            data.get("textbooks"),
            data.get("raw_html"),
            now,
            None,
        ),
    )
    await conn.commit()


async def save_error_to_db(
    conn: psycopg.AsyncConnection,  # type: ignore[type-arg]
    pkey: str,
    html: str,
    nendo: str,
) -> None:
    now = datetime.now(timezone.utc)
    await conn.execute(
        UPSERT_ERROR_SQL,
        (pkey, "PARSE_ERROR", int(nendo), "unknown", [], html, now),
    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Main crawler loop
# ---------------------------------------------------------------------------


async def run_crawler(
    nendo: str,
    conninfo: str,
    checkpoint_path: Path,
    limit: int | None = None,
) -> None:
    state = CrawlState(checkpoint_path)

    log.info(f"Fetching pKey list for nendo={nendo} ...")
    all_pkeys = await fetch_all_pkeys(nendo)
    log.info(f"Total pKeys collected: {len(all_pkeys)}")

    pending = [pk for pk in all_pkeys if not state.is_done(pk)]
    if limit is not None:
        pending = pending[:limit]

    skipped = len(all_pkeys) - len(pending)
    log.info(
        f"Pending: {len(pending)}  |  "
        f"Already done (skipped): {skipped}"
    )

    headers = {"User-Agent": USER_AGENT}
    rate_limiter = RateLimiter(requests_per_second=1.0)

    async with await psycopg.AsyncConnection.connect(conninfo) as db_conn:
        async with httpx.AsyncClient(headers=headers) as http_client:
            total = len(pending)
            for i, pkey in enumerate(pending, 1):
                await rate_limiter.wait()

                log.info(f"[{i}/{total}] pKey={pkey}")
                try:
                    html = await _fetch_html(http_client, pkey)
                    if html is None:
                        log.warning(f"  404 – skipping pKey={pkey}")
                        state.mark_done(pkey)
                        continue

                    data = parse_syllabus(html, pkey)
                    if data is None:
                        log.warning(
                            f"  Parse failed – saving raw HTML for pKey={pkey}"
                        )
                        await save_error_to_db(db_conn, pkey, html, nendo)
                    else:
                        await save_to_db(db_conn, data, nendo)
                        log.info(f"  Saved: {data['title'][:50]!r}")

                    state.mark_done(pkey)

                except Exception as exc:
                    log.error(f"  Fatal error on pKey={pkey}: {exc}")
                    state.save()
                    raise

    state.save()
    log.info(f"Crawl complete. Processed {total} syllabuses.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _build_conninfo() -> str:
    if url := os.environ.get("DATABASE_URL"):
        return url
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB", "waseda_syllabus")
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Waseda Syllabus Crawler")
    parser.add_argument(
        "--nendo", default="2026", help="Academic year to crawl (e.g. 2026)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of syllabuses (for testing)",
    )
    parser.add_argument(
        "--checkpoint",
        default="crawl_state.json",
        help="Path to checkpoint file",
    )
    args = parser.parse_args()

    asyncio.run(
        run_crawler(
            nendo=args.nendo,
            conninfo=_build_conninfo(),
            checkpoint_path=Path(args.checkpoint),
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
