import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.core.scheduler import setup_scheduler
from app.api.jobs import router
from app.services.ingestion import run_ingestion

def _setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    # Attach to our package logger only — avoids fighting uvicorn's root logger
    app_log = logging.getLogger("app")
    app_log.setLevel(logging.INFO)
    if not app_log.handlers:
        app_log.addHandler(handler)
    app_log.propagate = False  # don't double-log through uvicorn's root handler

_setup_logging()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_scheduler()
    # Run ingestion on startup if DB is empty
    from app.core.database import AsyncSessionLocal
    from app.models.job import Job
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count(Job.id)))).scalar_one()
    if count == 0:
        print("[startup] DB is empty — triggering ingestion", flush=True)
        log.info("DB is empty, running initial ingestion")
        await run_ingestion(initial=True)
    else:
        print(f"[startup] DB has {count} jobs — skipping ingestion", flush=True)
    yield
    from app.core.scheduler import scheduler
    scheduler.shutdown(wait=False)


app = FastAPI(title="Job Tracker API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"name": "JobRadar API", "docs": "/docs", "health": "/health"}
