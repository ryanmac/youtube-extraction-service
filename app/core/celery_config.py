# app/core/celery_config.py
from celery import Celery
from app.core.config import settings
import logging
import ssl

logger = logging.getLogger(__name__)


def create_celery_app():
    broker_url = settings.get_redis_url
    result_backend = settings.get_redis_url

    # Add SSL configuration for Redis
    broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
    redis_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

    celery_app = Celery(
        "worker",
        broker=broker_url,
        backend=result_backend,
        broker_use_ssl=broker_use_ssl,
        redis_backend_use_ssl=redis_backend_use_ssl,
        include=["app.services.youtube_scraper", "app.services.transcript_processor", "app.main"]
    )

    celery_app.conf.broker_connection_retry_on_startup = True
    celery_app.conf.broker_connection_max_retries = 10
    celery_app.conf.task_routes = {
        "app.services.youtube_scraper.start_channel_processing": {"queue": "celery"},
        "app.services.youtube_scraper.process_video": {"queue": "video-queue"},
        "app.services.transcript_processor.process_transcript": {"queue": "transcript-queue"},
    }

    celery_app.conf.update(
        task_track_started=True,
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        result_expires=3600,
        broker_transport_options={'visibility_timeout': 3600},
        broker_connection_retry=True,
        broker_pool_limit=None,
        broker_transport='redis',
        result_backend_transport='redis'
    )

    logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
    logger.info(f"Celery result backend: {celery_app.conf.result_backend}")

    return celery_app


celery_app = create_celery_app()
