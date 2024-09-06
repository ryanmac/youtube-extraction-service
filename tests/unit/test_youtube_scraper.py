# tests/unit/test_youtube_scraper.py
import pytest
from app.services.youtube_scraper import start_channel_processing
from unittest.mock import patch


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


@pytest.fixture
def mock_youtube_scraper():
    with patch('app.services.youtube_scraper.YoutubeScraper') as mock:
        yield mock


@pytest.fixture
def mock_pinecone():
    with patch('app.services.youtube_scraper.get_index_stats') as mock:
        yield mock


def test_start_channel_processing_with_url(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_get_channel_info,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Mock dependencies
    mock_get_channel_info.return_value = {
        "channel_id": "test_channel_id",
        "unique_video_count": 0,
        "total_embeddings": 0,
        "metadata": {
            "id": "test_channel_id",
            "snippet": {"title": "Test Channel", "customUrl": "@drwaku"}
        }
    }
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"
    mock_transcript_exists.side_effect = [False, False]

    # Test with channel URL
    result = start_channel_processing(channel_url="https://www.youtube.com/channel/@drwaku", video_limit=2)
    assert result == {'status': 'All videos processed', 'progress': 100, 'channel_id': 'test_channel_id'}
    mock_get_channel_info.assert_called_once_with('@drwaku')
    mock_youtube_scraper.return_value.get_video_ids.assert_called_once()
    assert mock_youtube_scraper.return_value.get_video_transcript.call_count == 2
    assert mock_store_embeddings.call_count == 2
    assert mock_redis_client.set.call_count == 2


def test_start_channel_processing_with_channel_id(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_get_channel_info,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Mock dependencies
    mock_get_channel_info.return_value = {
        "channel_id": "test_channel_id",
        "unique_video_count": 0,
        "total_embeddings": 0,
        "metadata": {
            "id": "test_channel_id",
            "snippet": {"title": "Test Channel", "customUrl": "@drwaku"}
        }
    }
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"
    mock_transcript_exists.side_effect = [False, False]

    # Test with channel ID
    result = start_channel_processing(channel_id="UCZf5IX90oe5gdPppMXGImwg", video_limit=2)
    assert result == {'status': 'All videos processed', 'progress': 100, 'channel_id': 'test_channel_id'}
    mock_get_channel_info.assert_called_with('UCZf5IX90oe5gdPppMXGImwg')
    mock_youtube_scraper.return_value.get_video_ids.assert_called_once()
    assert mock_youtube_scraper.return_value.get_video_transcript.call_count == 2
    assert mock_store_embeddings.call_count == 2
    assert mock_redis_client.set.call_count == 2


def test_start_channel_processing_invalid_url_format(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_get_channel_info,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Test with an invalid URL format
    with pytest.raises(ValueError, match="Invalid channel URL format: https://www.youtube.com/@drwaku"):
        start_channel_processing(channel_url="https://www.youtube.com/@drwaku", video_limit=2)
    mock_get_channel_info.assert_not_called()
    mock_youtube_scraper.return_value.get_video_ids.assert_not_called()
    assert mock_store_embeddings.call_count == 0
    assert mock_redis_client.set.call_count == 0


def test_start_channel_processing_missing_channel_info(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_get_channel_info,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Mock dependencies
    mock_get_channel_info.return_value = None

    # Test with channel URL that doesn't return channel info
    with pytest.raises(Exception, match="Channel metadata not found for @drwaku"):
        start_channel_processing(channel_url="https://www.youtube.com/channel/@drwaku", video_limit=2)
    mock_get_channel_info.assert_called_once_with('@drwaku')
    mock_youtube_scraper.return_value.get_video_ids.assert_not_called()
    assert mock_store_embeddings.call_count == 0
    assert mock_redis_client.set.call_count == 0
