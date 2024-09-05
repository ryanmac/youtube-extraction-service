# tests/unit/test_youtube_scraper.py
import pytest
from app.services.youtube_scraper import start_channel_processing
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_celery_task():
    with patch('celery.app.task.Task.update_state') as mock:
        yield mock


@pytest.fixture
def mock_get_channel_info():
    with patch('app.services.youtube_scraper.get_channel_info') as mock:
        yield mock


@pytest.fixture
def mock_transcript_exists():
    with patch('app.services.youtube_scraper.transcript_exists') as mock:
        yield mock


@pytest.fixture
def mock_store_embeddings():
    with patch('app.services.youtube_scraper.store_embeddings') as mock:
        yield mock


@pytest.fixture
def mock_redis_client():
    with patch('app.services.youtube_scraper.redis_client') as mock:
        yield mock


def test_start_channel_processing(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_get_channel_info,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    mock_get_channel_info.return_value = {
        "channel_id": "test_channel_id",
        "unique_video_count": 0,
        "total_embeddings": 0,
        "metadata": {
            "id": "test_channel_id",
            "snippet": {"title": "Test Channel"}
        }
    }
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"

    # Mock transcript_exists to return False for both videos
    mock_transcript_exists.side_effect = [False, False]

    mock_index = MagicMock()
    mock_pinecone.return_value.Index.return_value = mock_index

    result = start_channel_processing("https://www.youtube.com/@drwaku", 2)

    assert result == {'status': 'All videos processed', 'progress': 100, 'channel_id': 'test_channel_id'}
    mock_get_channel_info.assert_called_once_with('@drwaku')
    mock_youtube_scraper.return_value.get_video_ids.assert_called_once()
    assert mock_youtube_scraper.return_value.get_video_transcript.call_count == 2
    assert mock_store_embeddings.call_count == 2
    assert mock_redis_client.set.call_count == 2
