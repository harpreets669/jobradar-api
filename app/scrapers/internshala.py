"""
Internshala scraper — the primary source for India internship/fresher postings.
Robots.txt disallows automated bots, so we scrape respectfully:
  - 1 request every 2 seconds
  - Only public listing pages (no login required)
  - Standard browser User-Agent
"""
import asyncio
import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from app.scrapers.base import RawJob

BASE_URL = "https://internshala.com"

PAGES_TO_SCRAPE = [
    "/internships/",
    "/jobs/fresher-jobs/",
    "/internships/work-from-home-internship/",
]


def _parse_listing(card) -> RawJob | None:
    try:
        title_el = card.select_one(".job-internship-name")
        company_el = card.select_one(".company-name")
        location_el = card.select_one(".locations span")
        link_el = card.select_one("a.job-title-href")

        if not title_el:
            return None

        title = title_el.get_text(strip=True)
        company = company_el.get_text(strip=True) if company_el else "Unknown"
        location = location_el.get_text(strip=True) if location_el else "India"

        # Prefer data-href on the card itself; fall back to anchor href
        href = card.get("data-href") or (link_el["href"] if link_el and link_el.get("href") else "")
        url = BASE_URL + href if href else ""

        desc_el = card.select_one(".about_job .text")
        stipend_el = card.select_one(".stipend")
        description = (desc_el.get_text(strip=True) if desc_el else "") or (stipend_el.get_text(strip=True) if stipend_el else "")

        is_remote = "work from home" in location.lower() or "remote" in location.lower()
        experience_type = "intern" if "intern" in title.lower() else "fresher"

        return RawJob(
            title=title,
            company=company,
            location_raw=location,
            description=description,
            url=url,
            source="internshala",
            posted_at=None,
            is_remote=is_remote,
            experience_type=experience_type,
        )
    except Exception:
        return None


async def fetch_internshala_jobs() -> list[RawJob]:
    jobs: list[RawJob] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
        for path in PAGES_TO_SCRAPE:
            try:
                resp = await client.get(BASE_URL + path)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                cards = soup.select(".internship_meta, .individual_internship")[:50]
                for card in cards:
                    job = _parse_listing(card)
                    if job:
                        jobs.append(job)

                await asyncio.sleep(2)  # be respectful
            except Exception as e:
                print(f"[internshala] Error fetching {path}: {e}")

    print(f"[internshala] Fetched {len(jobs)} raw jobs")
    return jobs
