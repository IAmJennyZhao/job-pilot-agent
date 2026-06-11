from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import ai, dashboard, interview, jobs, profile, skill_gaps, study_plans


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CareerPilot Agent API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(jobs.router)
    app.include_router(profile.router)
    app.include_router(skill_gaps.router)
    app.include_router(study_plans.router)
    app.include_router(dashboard.router)
    app.include_router(interview.router)
    app.include_router(ai.router)
    return app


app = create_app()
