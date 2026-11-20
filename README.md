# jobradar-api

FastAPI backend for JobRadar — a live tracker for fresher jobs and internships across India. Scrapes multiple sources daily, deduplicates listings, and uses Claude Haiku to tag each post by role and city.

## Stack

- **FastAPI** — async Python web framework
- **PostgreSQL** — job storage (via SQLAlchemy async + asyncpg)
- **APScheduler** — daily ingestion cron (runs inside the process)
- **Claude Haiku** — LLM tagging (~$0.13 per 1,000 jobs)
- **httpx + feedparser + BeautifulSoup** — scraping and RSS parsing

## Project Structure

```
app/
├── core/               # Infrastructure
│   ├── config.py       # Settings from environment variables
│   ├── database.py     # SQLAlchemy engine, session factory, init_db
│   └── scheduler.py    # APScheduler setup (daily 06:00 IST)
│
├── models/             # Database table definitions
│   └── job.py          # Job table (SQLAlchemy ORM model)
│
├── schemas/            # API shapes (request/response)
│   └── job.py          # Pydantic models: JobOut, JobListResponse, StatsResponse
│
├── api/                # HTTP route handlers
│   └── jobs.py         # GET /api/jobs, GET /api/stats, POST /api/refresh
│
├── scrapers/           # Data fetching from external sources
│   ├── base.py         # RawJob dataclass (common format across scrapers)
│   ├── adzuna.py       # Adzuna Jobs API (official, free tier)
│   ├── rss.py          # RSS feeds: TimesJobs, Remotive
│   └── internshala.py  # HTML scraper for Internshala listings
│
├── services/           # Business logic
│   ├── ingestion.py    # Orchestrates: fetch → dedup → tag → save
│   ├── tagger.py       # Claude Haiku batched LLM tagging
│   └── deduplicator.py # SHA-256 hash-based deduplication
│
└── main.py             # App entry point, lifespan, CORS middleware
```

## How it works

1. **Startup** — `main.py` runs `init_db()` (creates tables if missing), then starts APScheduler and runs an initial ingestion if the DB is empty.
2. **Ingestion** (`services/ingestion.py`) — fetches from all scrapers concurrently, deduplicates against existing DB records, calls the LLM tagger in batches of 10, then saves new jobs to PostgreSQL.
3. **Daily refresh** — APScheduler triggers `run_ingestion()` at 06:00 IST every day.
4. **API** — FastAPI serves paginated job listings with search and filter support.

## Setup

**Prerequisites**: Python 3.10+, PostgreSQL running locally

```bash
# 1. Create the database
psql postgres -c "CREATE DATABASE jobradar;"

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, ADZUNA_APP_ID, ADZUNA_APP_KEY

# 4. Run
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for LLM tagging |
| `ADZUNA_APP_ID` | Yes | From developer.adzuna.com (free) |
| `ADZUNA_APP_KEY` | Yes | From developer.adzuna.com (free) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user@host:5432/jobradar` |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins (e.g. your Vercel URL) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/jobs` | Paginated job list. Supports `q`, `city`, `role`, `source`, `experience`, `page`, `page_size` |
| `GET` | `/api/stats` | Total count, source breakdown, top cities and roles, last refresh time |
| `POST` | `/api/refresh` | Manually trigger ingestion (runs in background) |
| `GET` | `/health` | Liveness check |

## Deployment

Deploy on Railway. Set all environment variables in the Railway dashboard — the `DATABASE_URL` is provided automatically when you add a PostgreSQL plugin.
