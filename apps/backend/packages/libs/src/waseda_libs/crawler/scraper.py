"""HTTP scraping layer for Waseda syllabus site.

Responsible only for fetching:
- pKey list from JAA103.php (POST, paginated)
- Syllabus HTML from JAA104.php (GET, rate-limited, with retry)
"""

import asyncio
import logging
import re
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

BASE_URL = "https://www.wsl.waseda.jp/syllabus"
USER_AGENT = "WasedaSyllabusMCP/1.0 (research purpose)"

_PKEY_RE = re.compile(r"post_submit\('JAA104DtlSubCon',\s*'([A-Za-z0-9]{28})'")
_PAGE_ITEMS = 100


async def fetch_all_pkeys(
    nendo: str, max_pkeys: int | None = None
) -> list[str]:
    """Collect pKeys from JAA103.php via POST.

    pKeys are embedded in onclick attributes of the search result table.
    Pagination is driven by the ``p_page`` POST parameter.
    Stops early when ``max_pkeys`` is reached.
    """
    url = f"{BASE_URL}/JAA103.php"
    pkeys: list[str] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        page_num = 1
        while True:
            resp = await client.post(
                url,
                data={
                    "pLng": "jp",
                    "nendo": nendo,
                    "ControllerParameters": "JAA103SubCon",
                    "p_number": str(_PAGE_ITEMS),
                    "p_page": str(page_num),
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            found = _PKEY_RE.findall(resp.text)

            if not found:
                log.info(f"  Page {page_num}: no pKeys — collection complete.")
                break

            pkeys.extend(found)
            log.info(f"  Page {page_num}: {len(found)} pKeys (total: {len(pkeys)})")

            if max_pkeys is not None and len(pkeys) >= max_pkeys:
                break

            if len(found) < _PAGE_ITEMS:
                break

            page_num += 1
            await asyncio.sleep(0.5)

    # Deduplicate, preserve order
    seen: set[str] = set()
    return [pk for pk in pkeys if not (pk in seen or seen.add(pk))]  # type: ignore[func-returns-value]


class RateLimiter:
    """Enforces a minimum interval between requests."""

    def __init__(self, requests_per_second: float = 1.0) -> None:
        self.interval = 1.0 / requests_per_second
        self._last: float = 0.0

    async def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.interval:
            await asyncio.sleep(self.interval - elapsed)
        self._last = time.monotonic()


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def fetch_syllabus_html(client: httpx.AsyncClient, pkey: str) -> str | None:
    """Fetch syllabus detail HTML for a given pKey. Returns None on 404."""
    url = f"{BASE_URL}/JAA104.php?pKey={pkey}&pLng=jp"
    try:
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
