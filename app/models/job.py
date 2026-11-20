import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dedup_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200))
    location_raw: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(100), default="", index=True)
    role_category: Mapped[str] = mapped_column(String(100), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), index=True)
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    experience_type: Mapped[str] = mapped_column(String(50), default="fresher")

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
