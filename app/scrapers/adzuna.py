"""
Adzuna Jobs API — official free tier (developer.adzuna.com).
Covers India with good fresher/entry-level coverage.
"""
import httpx
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
from app.scrapers.base import RawJob

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/{page}"

def _campus_query() -> str:
    # Campus batches span two years: current and next (e.g. "2026 2027" in Nov 2026)
    year = datetime.now().year
    return f"campus hiring {year} {year + 1}"

FRESHER_QUERIES = [
    "fresher software engineer",
    "fresher data analyst",
    "internship engineering",
    "fresher marketing",
    "entry level software",
    "internship data science",
    "fresher finance",
    _campus_query(),
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _fetch_page(client: httpx.AsyncClient, query: str, page: int, max_days_old: int = 2) -> dict:
    resp = await client.get(
        BASE_URL.format(page=page),
        params={
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": 50,
            "what": query,
            "content-type": "application/json",
            "max_days_old": max_days_old,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


MAX_JOBS = 500  # hard cap per run to bound memory and LLM cost

async def fetch_adzuna_jobs(max_days_old: int = 2) -> list[RawJob]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        print("[adzuna] No credentials configured, skipping.")
        return []

    jobs: list[RawJob] = []
    async with httpx.AsyncClient() as client:
        for query in FRESHER_QUERIES:
            if len(jobs) >= MAX_JOBS:
                break
            try:
                data = await _fetch_page(client, query, page=1, max_days_old=max_days_old)
                for item in data.get("results", []):
                    posted_at = None
                    if item.get("created"):
                        try:
                            posted_at = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
                        except Exception:
                            pass

                    location = item.get("location", {})
                    loc_parts = location.get("display_name", "") or ""
                    title_str = item.get("title", "").strip()
                    desc_str = (item.get("description") or "")[:500]
                    is_remote = "remote" in (loc_parts + title_str + desc_str).lower()

                    jobs.append(RawJob(
                        title=title_str,
                        company=item.get("company", {}).get("display_name", "Unknown"),
                        location_raw=loc_parts,
                        description=desc_str,
                        url=item.get("redirect_url", ""),
                        source="adzuna",
                        posted_at=posted_at,
                        is_remote=is_remote,
                    ))
            except Exception as e:
                print(f"[adzuna] Error fetching query '{query}': {e}")

    print(f"[adzuna] Fetched {len(jobs)} raw jobs")
    return jobs
