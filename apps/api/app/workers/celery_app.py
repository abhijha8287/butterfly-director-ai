from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings
from app.workers.queues import ALL_QUEUES, MAINTENANCE_QUEUE

settings = get_settings()

celery_app = Celery(
    "butterfly_director",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.maintenance_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue=MAINTENANCE_QUEUE,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.beat_schedule = {
    "reap-stale-jobs": {
        "task": "app.workers.tasks.maintenance_tasks.reap_stale_jobs",
        "schedule": crontab(minute="*/5"),
    },
}

ACTIVE_QUEUES = ALL_QUEUES
