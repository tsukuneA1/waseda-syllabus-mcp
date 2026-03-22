"""HTML parser for Waseda syllabus detail pages (JAA104.php)."""

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

SEMESTER_MAP: dict[str, list[str]] = {
    "spring": ["春学期", "Spring", "前期"],
    "fall": ["秋学期", "Fall", "後期"],
    "full": ["通年", "Full Year", "春学期・秋学期"],
}


def _normalize(text: str) -> str:
    text = text.replace("\u3000", " ")  # full-width space → ASCII space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _detect_semester(text: str) -> str:
    for key, keywords in SEMESTER_MAP.items():
        if any(kw in text for kw in keywords):
            return key
    return "unknown"


def _parse_schedule_table(tag: Tag) -> list[dict[str, str]]:
    """Parse the inner schedule table into a list of dicts."""
    rows: list[dict[str, str]] = []
    headers: list[str] = []

    for tr in tag.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        texts = [_normalize(c.get_text()) for c in cells]

        # First row with only th tags → header
        if all(c.name == "th" for c in cells) and not headers:
            headers = texts
            continue

        if headers and len(texts) == len(headers):
            rows.append(dict(zip(headers, texts)))
        else:
            rows.append({"content": " ".join(t for t in texts if t)})

    return rows


def _extract_instructors(tds: list[Tag]) -> list[str]:
    """Extract instructor names from one or more td tags."""
    raw: list[str] = []
    for td in tds:
        raw.extend(re.split(r"[,、\n/／]", _normalize(td.get_text())))
    return [name.strip() for name in raw if name.strip()]


def parse_syllabus(html: str, pkey: str) -> dict[str, Any] | None:
    """Parse a JAA104.php response and return a field dict, or None on error."""
    soup = BeautifulSoup(html, features="xml")

    # Detect error pages
    body_text = soup.get_text()
    if (
        "該当するシラバスが見つかりません" in body_text
        or "No syllabus found" in body_text
        or not soup.find("table")
    ):
        return None

    result: dict[str, Any] = {
        "pkey": pkey,
        "title": "",
        "title_en": None,
        "year": 0,
        "semester": "unknown",
        "credits": None,
        "department": None,
        "instructors": [],
        "description": None,
        "objectives": None,
        "schedule": None,
        "evaluation": None,
        "textbooks": None,
        "raw_html": html,
    }

    for row in soup.find_all("tr"):
        ths = row.find_all("th")
        tds = row.find_all("td")
        if not ths or not tds:
            continue

        field = _normalize(ths[0].get_text())
        value = _normalize(tds[0].get_text())

        if ("授業科目名" in field or "科目名" in field) and "英語" not in field:
            if value:
                result["title"] = value

        elif "英語" in field and ("科目名" in field or "授業科目" in field):
            result["title_en"] = value or None

        elif "開講年度" in field:
            m = re.search(r"(\d{4})", value)
            if m:
                result["year"] = int(m.group(1))

        elif "学期" in field or "開講時期" in field:
            result["semester"] = _detect_semester(value)

        elif "単位" in field:
            m = re.search(r"(\d+)", value)
            if m:
                result["credits"] = int(m.group(1))

        elif "担当教員" in field or "教員名" in field:
            result["instructors"] = _extract_instructors(tds)

        elif ("配当学部" in field or "学部" in field) and "担当" not in field:
            result["department"] = value or None

        elif "授業概要" in field or ("概要" in field and "授業" in field):
            result["description"] = value or None

        elif "到達目標" in field or "学習目標" in field:
            result["objectives"] = value or None

        elif "授業計画" in field:
            inner_table = tds[0].find("table")
            if inner_table:
                parsed = _parse_schedule_table(inner_table)
            else:
                parsed = [{"content": value}] if value else []
            result["schedule"] = parsed if parsed else None

        elif "成績評価" in field:
            result["evaluation"] = value or None

        elif "テキスト" in field or "教科書" in field:
            result["textbooks"] = value or None

    # Fallback: try to get title from <h2> or <title>
    if not result["title"]:
        for tag in ("h2", "h1", "title"):
            t = soup.find(tag)
            if t:
                result["title"] = _normalize(t.get_text())
                break

    # Extract year from pKey if not found (positions 12-16 are the 4-digit year)
    if result["year"] == 0 and len(pkey) == 28:
        candidate = pkey[12:16]
        if candidate.isdigit() and 2000 <= int(candidate) <= 2100:
            result["year"] = int(candidate)

    if not result["title"] or result["year"] == 0:
        return None

    return result
