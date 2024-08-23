# conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
import redis
from unittest.mock import patch


@pytest.fixture(scope="session")
def test_client():
    return TestClient(app)


@pytest.fixture(scope="session")
def redis_client():
    return redis.Redis.from_url(settings.REDIS_URL)


@pytest.fixture(scope="function")
def mock_pinecone():
    with patch("app.services.pinecone_service.Pinecone") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_celery():
    with patch("app.core.celery_config.celery_app") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_youtube_scraper():
    with patch("app.services.youtube_scraper.YoutubeScraper") as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_openai():
    with patch("openai.Embedding.create") as mock:
        mock.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        yield mock
