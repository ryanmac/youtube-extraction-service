import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
from app.core.celery_config import celery_app
from celery import shared_task
from contextlib import asynccontextmanager


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Application is starting up")
    logger.info(f"Celery broker URL: {celery_app.conf.broker_url}")
    logger.info(f"Celery result backend: {celery_app.conf.result_backend}")
    logger.info(f"Redis URL: {settings.REDIS_URL}")

    yield  # Control is returned to FastAPI for handling requests

    # Shutdown logic
    logger.info("Application is shutting down")


app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "https://channel-chat-pi.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@shared_task
def test_task():
    logger.info("Test task executed")
    return "Task completed"


@app.get("/test-celery")
async def test_celery():
    result = test_task.delay()
    return {"message": "Test task queued", "task_id": result.id}


@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "YouTube Extraction Service", "status": "operational"}
