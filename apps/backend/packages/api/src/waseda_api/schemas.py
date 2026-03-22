from typing import Optional

from pydantic import BaseModel


class CourseSummary(BaseModel):
    pkey: str
    title: str
    title_en: Optional[str]
    instructors: list[str]
    semester: str
    credits: Optional[int]
    department: Optional[str]
    year: int
