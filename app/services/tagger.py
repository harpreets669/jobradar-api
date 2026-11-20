"""
Tags each job with role_category and city using Claude Haiku.
Batches 10 jobs per API call to minimize cost.

Cost estimate at claude-haiku-5-5 rates ($0.80/M in, $4/M out):
  ~600 tokens input + ~200 tokens output per batch of 10
  → ~$0.13 per 1,000 jobs
"""
import json
import asyncio
from datetime import datetime, timezone
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.scrapers.base import RawJob

ROLE_CATEGORIES = [
    "Software Engineer",           # includes DevOps, SRE, Cloud, Infrastructure, QA, Mobile
    "Engineering",                 # structural, mechanical, civil, electrical, chemical, etc.
    "Data Analyst",
    "Data Science / ML",
    "Product Management",
    "Marketing",
    "Sales",
    "Design / UI-UX",
    "Finance / Accounting",
    "Human Resources",
    "Operations",
    "Content Writing",
    "Customer Support",
    "Business Development",
    "Research",
    "Other",
]

SYSTEM_PROMPT = """You are a job categorization assistant. Given a list of job listings, extract:
1. role_category: Choose the single best match from this list:
   {categories}

   Mapping rules:
   - DevOps, SRE, Cloud Engineer, Infrastructure, Platform Engineer, QA/SDET, Mobile Developer → "Software Engineer"
   - Structural, Mechanical, Civil, Electrical, Chemical, Manufacturing, Industrial Engineer → "Engineering"
   - Apprentice/Trainee roles: map by the engineering domain (software → "Software Engineer", non-software → "Engineering (Non-Software)")
   - "Jr.", "Associate", "Intern" prefixes do not change the category — classify by the core role

2. city: The primary Indian city name, normalized to its canonical English name:
   - Bengaluru or Bengaluru Urban → "Bangalore"
   - Gurugram → "Gurgaon"
   - Bombay → "Mumbai"
   - Madras → "Chennai"
   - Calcutta → "Kolkata"
   - Delhi NCR, NCR, New Delhi → "Delhi"
   Other common cities: "Hyderabad", "Pune", "Noida", "Ahmedabad", "Jaipur", "Indore"
   Use "Remote" for work-from-home. Use "Pan India" if multiple cities or location is unclear.

Respond with a JSON array of objects with keys "role_category" and "city", in the same order as the input. No extra text.""".format(
    categories="\n   ".join(ROLE_CATEGORIES)
)

# Deterministic fallback — catches anything the LLM still gets wrong
CITY_ALIASES: dict[str, str] = {
    "bengaluru": "Bangalore",
    "bengaluru urban": "Bangalore",
    "gurugram": "Gurgaon",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "new delhi": "Delhi",
    "delhi ncr": "Delhi",
    "ncr": "Delhi",
}


def _normalize_city(city: str) -> str:
    city = city.strip()
    # Strip state/country suffix: "Bangalore, Karnataka" → "Bangalore"
    if "," in city:
        city = city.split(",")[0].strip()
    return CITY_ALIASES.get(city.lower(), city)


def _make_user_message(batch: list[RawJob]) -> str:
    items = []
    for i, job in enumerate(batch):
        items.append(
            f"{i+1}. Title: {job.title}\n"
            f"   Company: {job.company}\n"
            f"   Location: {job.location_raw}\n"
            f"   Description: {job.description[:200]}"
        )
    return "\n\n".join(items)


async def _tag_batch(client: AsyncAnthropic, batch: list[RawJob]) -> list[dict]:
    try:
        response = await client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _make_user_message(batch)}],
        )
        if not response.content:
            raise ValueError("Empty content list in response")
        # Claude 5 models return a thinking block first — find the actual text block
        raw = None
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw = block.text
                break
        if raw is None:
            types = [getattr(b, "type", "?") for b in response.content]
            raise ValueError(f"No text block found (block types={types}, stop_reason={response.stop_reason})")
        raw = raw.strip()
        # Claude sometimes wraps in ```json ... ```
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tags = json.loads(raw)
        return [
            {
                "role_category": t.get("role_category", "Other"),
                "city": _normalize_city(t.get("city", "Pan India")),
            }
            for t in tags
        ]
    except Exception as e:
        print(f"[tagger] Batch tagging failed: {e}")
        return [{"role_category": "Other", "city": "Pan India"}] * len(batch)


async def tag_jobs(jobs: list[RawJob], batch_size: int = 10) -> list[dict]:
    """Returns list of {role_category, city} dicts in same order as input."""
    if not settings.anthropic_api_key:
        print("[tagger] No Anthropic API key, using placeholder tags.")
        return [{"role_category": "Other", "city": "Pan India"}] * len(jobs)

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    results: list[dict] = []

    batches = [jobs[i:i + batch_size] for i in range(0, len(jobs), batch_size)]
    for i, batch in enumerate(batches):
        tags = await _tag_batch(client, batch)
        results.extend(tags)
        # Small delay to avoid rate limits
        if i < len(batches) - 1:
            await asyncio.sleep(0.5)

    return results
