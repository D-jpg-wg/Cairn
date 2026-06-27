from celery import Celery
from app.core.config import setting


celery_app = Celery(
    "cairn",
    broker=setting.celery_broker_url,
    include=["app.worker.tasks"],
)
