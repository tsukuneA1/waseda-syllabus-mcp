from typing import Annotated, Literal, Optional

from db.gen.syllabuses import AsyncQuerier
from fastapi import APIRouter, Query

from waseda_api.deps import DbConn
from waseda_api.schemas import CourseSummary

router = APIRouter(prefix="/courses", tags=["courses"])


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
    querier = AsyncQuerier(conn)
    results = []
    async for row in querier.search_courses(
        dollar_1=query,  # type: ignore[arg-type]
        dollar_2=year,  # type: ignore[arg-type]
        dollar_3=semester,  # type: ignore[arg-type]
        limit=limit,
    ):
        results.append(
            CourseSummary(
                pkey=row.pkey,
                title=row.title,
                title_en=row.title_en,
                year=row.year,
                semester=row.semester,
                credits=row.credits,
                department=row.department,
                instructors=row.instructors,
            )
        )
    return results
