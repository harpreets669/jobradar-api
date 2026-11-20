"""
Orchestrates: fetch → deduplicate → persist (untagged) → LLM tag → update.
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.job import Job
from app.services.deduplicator import make_dedup_hash
from app.scrapers.adzuna import fetch_adzuna_jobs
from app.scrapers.rss import fetch_rss_jobs
from app.scrapers.internshala import fetch_internshala_jobs
from app.services.tagger import tag_jobs

log = logging.getLogger(__name__)


async def run_ingestion(initial: bool = False):
    print(f"[ingestion] run_ingestion called, initial={initial}", flush=True)
    log.info("Ingestion started — mode=%s", "initial" if initial else "daily")

    # On first run seed with 90 days of history; daily runs only fetch last 2 days
    adzuna_days = 90 if initial else 2

    rss_days = 90 if initial else 2

    # 1. Fetch from all sources concurrently
    adzuna_jobs, rss_jobs, internshala_jobs = await asyncio.gather(
        fetch_adzuna_jobs(max_days_old=adzuna_days),
        fetch_rss_jobs(max_days_old=rss_days),
        fetch_internshala_jobs(),
    )
    all_raw = adzuna_jobs + rss_jobs + internshala_jobs
    log.info(
        "Fetch complete — adzuna=%d rss=%d internshala=%d total=%d",
        len(adzuna_jobs), len(rss_jobs), len(internshala_jobs), len(all_raw),
    )

    if not all_raw:
        log.warning("No jobs fetched from any source")
        return

    # 2. Deduplicate by hash — only keep truly new ones
    new_jobs = []
    seen_hashes: set[str] = set()

    async with AsyncSessionLocal() as db:
        hashes = [make_dedup_hash(j.title, j.company, j.location_raw) for j in all_raw]
        existing = await db.execute(
            select(Job.dedup_hash).where(Job.dedup_hash.in_(hashes))
        )
        existing_hashes = {row[0] for row in existing}

    already_in_db = 0
    within_batch_dupes = 0
    for raw_job in all_raw:
        h = make_dedup_hash(raw_job.title, raw_job.company, raw_job.location_raw)
        if h in existing_hashes:
            already_in_db += 1
        elif h in seen_hashes:
            within_batch_dupes += 1
        else:
            seen_hashes.add(h)
            new_jobs.append((raw_job, h))

    log.info(
        "Dedup complete — raw=%d dropped_already_in_db=%d dropped_cross_source=%d new=%d",
        len(all_raw), already_in_db, within_batch_dupes, len(new_jobs),
    )

    if not new_jobs:
        log.info("Nothing new to add, ingestion done")
        return

    # 3. Tag with LLM
    raw_list = [j for j, _ in new_jobs]
    tags = await tag_jobs(raw_list)

    # 4. Persist in chunks so a single transaction never holds too many rows
    CHUNK_SIZE = 50
    now = datetime.now(timezone.utc)
    saved = 0

    pairs = list(zip(new_jobs, tags))
    for i in range(0, len(pairs), CHUNK_SIZE):
        chunk = pairs[i : i + CHUNK_SIZE]
        async with AsyncSessionLocal() as db:
            for (raw_job, h), tag in chunk:
                db.add(Job(
                    dedup_hash=h,
                    title=raw_job.title,
                    company=raw_job.company,
                    location_raw=raw_job.location_raw,
                    city=tag.get("city", "Pan India"),
                    role_category=tag.get("role_category", "Other"),
                    description=raw_job.description,
                    url=raw_job.url,
                    source=raw_job.source,
                    is_remote=raw_job.is_remote,
                    experience_type=raw_job.experience_type,
                    posted_at=raw_job.posted_at,
                    tagged_at=now,
                ))
            await db.commit()
            saved += len(chunk)

    log.info("Ingestion complete — saved=%d", saved)
