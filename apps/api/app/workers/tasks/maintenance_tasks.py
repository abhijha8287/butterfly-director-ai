from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config.logging import get_logger
from app.db.base import sync_session_factory
from app.db.models.enums import JobStatus
from app.db.models.job import Job
from app.workers.celery_app import celery_app
from app.workers.queues import MAINTENANCE_QUEUE

logger = get_logger(__name__)

STALE_JOB_TIMEOUT_MINUTES = 60


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.reap_stale_jobs", queue=MAINTENANCE_QUEUE
)
def reap_stale_jobs() -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=STALE_JOB_TIMEOUT_MINUTES)
    reaped = 0

    with sync_session_factory() as session:
        stmt = select(Job).where(Job.status == JobStatus.RUNNING, Job.started_at < cutoff)
        stale_jobs = session.execute(stmt).scalars().all()

        for job in stale_jobs:
            job.status = JobStatus.FAILED
            job.error_message = (
                f"Job exceeded {STALE_JOB_TIMEOUT_MINUTES}m timeout and was reaped "
                "by the maintenance task"
            )
            job.finished_at = datetime.now(UTC)
            reaped += 1

        session.commit()

    logger.info("stale_jobs_reaped", count=reaped)
    return reaped
