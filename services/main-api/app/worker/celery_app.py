from celery import Celery
from app.core.config import setting


celery_app = Celery(
    "cairn",
    broker=setting.celery_broker_url,
    include=["app.worker.tasks"],
)

celery_app.conf.beat_schedule = {
    "sweep-stuck-pending": {
        "task": "app.worker.tasks.sweep_stuck_pending",
        "schedule": 60.0,
    }
}
