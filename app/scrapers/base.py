from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawJob:
    title: str
    company: str
    location_raw: str
    description: str
    url: str
    source: str
    posted_at: datetime | None = None
    is_remote: bool = False
    experience_type: str = "fresher"
