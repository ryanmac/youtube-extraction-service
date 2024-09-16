# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
import redis
from unittest.mock import patch, MagicMock


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
    with patch("app.utils.embedding_utils.client.embeddings.create") as mock:
        mock.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        yield mock


@pytest.fixture
def mock_openai_embedding(mocker):
    mock = mocker.patch('app.utils.embedding_utils.generate_embedding')
    mock.return_value = [0.1] * 1536  # Return a valid embedding
    return mock


@pytest.fixture(scope="session")
def api_key_header():
    return {"Authorization": f"Bearer {settings.YES_API_KEY}"}


@pytest.fixture
def mock_celery_task():
    with patch('celery.app.task.Task.apply_async') as mock:
        mock.return_value.get = MagicMock()
        yield mock


@pytest.fixture
def mock_openai_client(mocker):
    mock_client = mocker.patch('app.utils.embedding_utils.client', autospec=True)
    mock_embeddings = MagicMock()
    mock_client.embeddings.create.return_value = mock_embeddings
    mock_embeddings.data = [MagicMock(embedding=[0.1] * 1536)]
    return mock_client


@pytest.fixture
def mock_generate_embedding():
    with patch('app.services.pinecone_service.generate_embedding') as mock:
        mock.return_value = [0.1] * 1536
        yield mock


@pytest.fixture
def mock_pinecone_query(mocker):
    mock = mocker.patch('app.services.pinecone_service.index.query')
    mock.side_effect = [
        # First call (channel existence check)
        {
            "matches": [{"id": "dummy_id"}]
        },
        # Second call (actual query for relevant chunks)
        {
            "matches": [
                {
                    "id": "video1_0",
                    "score": 0.9,
                    "metadata": {"text": "This is a test transcript.", "channel_id": "test_channel"}
                }
            ]
        }
    ]
    return mock
