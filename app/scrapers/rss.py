"""
RSS feed scrapers for Indian job boards.
RSS is the intended public consumption mechanism for these feeds.
"""
import feedparser
import httpx
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from app.scrapers.base import RawJob

# Public RSS feeds — these are designed to be fetched by aggregators
RSS_FEEDS = [
    # TimesJobs URLs removed — RSS endpoints returned 404 as of Nov 2026
    {
        "name": "Remotive India Remote",
        "url": "https://remotive.com/remote-jobs/feed?category=software-dev&location=india",
        "source": "remotive",
        "fresher_only": True,   # mixed experience levels — keyword-filter entries
        "india_only": True,     # location check: drop non-India geo-locked jobs
    },
    {
        "name": "Remotive All India",
        "url": "https://remotive.com/remote-jobs/feed?location=india",
        "source": "remotive",
        "fresher_only": True,
        "india_only": True,
    },
]

# Location strings that indicate a job is locked to a non-India geography
NON_INDIA_LOCATIONS = {
    "usa", "united states", "us only", "uk", "united kingdom", "canada",
    "australia", "europe", "germany", "france", "singapore", "brazil",
    "latin america", "latam", "nigeria", "africa",
}

def _is_india_compatible(location: str) -> bool:
    """Returns True if location is India, Worldwide/Remote, or unspecified."""
    loc = location.lower()
    # Explicitly India → keep
    if "india" in loc:
        return True
    # Worldwide / Remote with no geo-lock → keep (Indian candidates can apply)
    if loc in ("worldwide", "remote", "", "anywhere"):
        return True
    # Explicitly another country → drop
    if any(excl in loc for excl in NON_INDIA_LOCATIONS):
        return False
    # Unknown location string → keep (benefit of the doubt)
    return True

FRESHER_KEYWORDS = {
    "fresher", "intern", "internship", "trainee", "graduate", "entry level",
    "entry-level", "junior", "0-1 year", "0-2 year", "campus", "placement",
}

def _is_fresher_role(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in FRESHER_KEYWORDS)


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return None


async def fetch_rss_jobs(max_days_old: int = 2) -> list[RawJob]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days_old)
    jobs: list[RawJob] = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        for feed_config in RSS_FEEDS:
            try:
                resp = await client.get(
                    feed_config["url"],
                    headers={"User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)"},
                )
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)

                for entry in feed.entries:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    # Skip entries older than cutoff if date is available
                    posted_at = _parse_date(entry)
                    if posted_at and posted_at < cutoff:
                        continue

                    # Try to extract company from title (common format: "Title at Company")
                    company = "Unknown"
                    if " at " in title:
                        parts = title.rsplit(" at ", 1)
                        title = parts[0].strip()
                        company = parts[1].strip()

                    summary = entry.get("summary", "") or ""
                    # Strip HTML tags crudely
                    import re
                    summary = re.sub(r"<[^>]+>", " ", summary)
                    summary = re.sub(r"\s+", " ", summary).strip()[:500]

                    # For feeds with mixed experience levels, skip non-fresher roles
                    if feed_config.get("fresher_only") and not _is_fresher_role(title, summary):
                        continue

                    location = entry.get("location", "") or ""

                    # Drop jobs geo-locked to non-India countries
                    if feed_config.get("india_only") and not _is_india_compatible(location):
                        continue
                    is_remote = "remote" in (location + title + summary).lower()

                    jobs.append(RawJob(
                        title=title,
                        company=company,
                        location_raw=location or "India",
                        description=summary,
                        url=entry.get("link", ""),
                        source=feed_config["source"],
                        posted_at=posted_at,  # already parsed above
                        is_remote=is_remote,
                        experience_type="intern" if "intern" in title.lower() else "fresher",
                    ))

            except Exception as e:
                print(f"[rss] Error fetching {feed_config['name']}: {e}")

    print(f"[rss] Fetched {len(jobs)} raw jobs from RSS feeds")
    return jobs
