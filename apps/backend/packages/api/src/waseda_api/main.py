from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from waseda_api.deps import get_engine  # noqa: E402
from waseda_api.routers import courses  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_engine()  # initialize engine on startup
    yield
    engine = get_engine()
    await engine.dispose()


app = FastAPI(
    title="Waseda Syllabus API",
    description="早稲田大学シラバス検索 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(courses.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
