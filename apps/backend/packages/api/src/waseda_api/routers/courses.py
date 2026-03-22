from typing import Annotated, Literal, Optional

import sqlalchemy
from fastapi import APIRouter, Query

from waseda_api.deps import DbConn
from waseda_api.schemas import CourseSummary

router = APIRouter(prefix="/courses", tags=["courses"])

# Combined search query: keyword + optional year/semester filter
_SEARCH_SQL = """
SELECT pkey, title, title_en, year, semester, credits, department, instructors
FROM syllabuses
WHERE
    (:query::TEXT IS NULL OR (
        title ILIKE '%' || :query || '%'
        OR description ILIKE '%' || :query || '%'
        OR :query = ANY(instructors)
    ))
    AND (:year::SMALLINT IS NULL OR year = :year)
    AND (:semester::VARCHAR IS NULL OR semester = :semester)
ORDER BY year DESC, title
LIMIT :limit
"""


@router.get("/search", response_model=list[CourseSummary])
async def search_courses(
    conn: DbConn,
    query: Annotated[Optional[str], Query(description="検索キーワード（科目名・教員名・説明文）")] = None,
    year: Annotated[Optional[int], Query(description="対象年度")] = None,
    semester: Annotated[
        Optional[Literal["spring", "fall", "full", "unknown"]],
        Query(description="開講学期"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="取得件数上限")] = 10,
) -> list[CourseSummary]:
    result = await conn.execute(
        sqlalchemy.text(_SEARCH_SQL),
        {"query": query, "year": year, "semester": semester, "limit": limit},
    )
    rows = result.fetchall()
    return [
        CourseSummary(
            pkey=row[0],
            title=row[1],
            title_en=row[2],
            year=row[3],
            semester=row[4],
            credits=row[5],
            department=row[6],
            instructors=row[7],
        )
        for row in rows
    ]
