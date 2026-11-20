from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import JobListResponse, JobOut, StatsResponse
from app.services.ingestion import run_ingestion

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    q: str = Query("", description="Search in title, company, description"),
    city: str = Query("", description="Filter by city"),
    role: str = Query("", description="Filter by role category"),
    source: str = Query("", description="Filter by source"),
    experience: str = Query("", description="Filter by experience type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Job)

    if q:
        pattern = f"%{q}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.description.ilike(pattern),
            )
        )
    if city:
        stmt = stmt.where(Job.city.ilike(f"%{city}%"))
    if role:
        stmt = stmt.where(Job.role_category == role)
    if source:
        stmt = stmt.where(Job.source == source)
    if experience:
        stmt = stmt.where(Job.experience_type == experience)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(desc(Job.fetched_at)).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return JobListResponse(
        total=total,
        page=page,
        page_size=page_size,
        jobs=[JobOut.model_validate(r) for r in rows],
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Job.id)))).scalar_one()

    # Source breakdown
    source_rows = (await db.execute(
        select(Job.source, func.count(Job.id)).group_by(Job.source)
    )).all()

    # Top cities
    city_rows = (await db.execute(
        select(Job.city, func.count(Job.id))
        .where(Job.city != "")
        .group_by(Job.city)
        .order_by(desc(func.count(Job.id)))
        .limit(10)
    )).all()

    # Top roles
    role_rows = (await db.execute(
        select(Job.role_category, func.count(Job.id))
        .where(Job.role_category != "")
        .group_by(Job.role_category)
        .order_by(desc(func.count(Job.id)))
        .limit(10)
    )).all()

    last_fetched = (await db.execute(
        select(func.max(Job.fetched_at))
    )).scalar_one()

    return StatsResponse(
        total_jobs=total,
        sources={r[0]: r[1] for r in source_rows},
        top_cities={r[0]: r[1] for r in city_rows},
        top_roles={r[0]: r[1] for r in role_rows},
        last_refreshed=last_fetched,
    )


@router.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """Manually trigger ingestion (useful for testing)."""
    background_tasks.add_task(run_ingestion, False)
    return {"message": "Ingestion started in background"}
