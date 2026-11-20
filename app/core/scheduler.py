from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.ingestion import run_ingestion

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def setup_scheduler():
    # Run daily at 6:00 AM IST
    scheduler.add_job(
        run_ingestion,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    print("[scheduler] Daily ingestion scheduled at 06:00 IST")
