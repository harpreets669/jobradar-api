from datetime import datetime
from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    title: str
    company: str
    city: str
    role_category: str
    description: str
    url: str
    source: str
    is_remote: bool
    experience_type: str
    posted_at: datetime | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    jobs: list[JobOut]


class StatsResponse(BaseModel):
    total_jobs: int
    sources: dict[str, int]
    top_cities: dict[str, int]
    top_roles: dict[str, int]
    last_refreshed: datetime | None
