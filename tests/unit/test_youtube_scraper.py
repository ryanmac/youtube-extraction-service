# tests/unit/test_youtube_scraper.py
import pytest
from app.services.youtube_scraper import start_channel_processing
from unittest.mock import patch


@pytest.fixture
def mock_celery_task():
    with patch('celery.app.task.Task.update_state') as mock:
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


def test_start_channel_processing_with_channel_id(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Mock dependencies
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"
    mock_transcript_exists.side_effect = [False, False]

    # Test with channel ID
    result = start_channel_processing(channel_id="UCZf5IX90oe5gdPppMXGImwg", video_limit=2)
    assert result == {'status': 'All videos processed', 'progress': 100, 'channel_id': 'UCZf5IX90oe5gdPppMXGImwg'}
    mock_youtube_scraper.return_value.get_video_ids.assert_called_once()
    assert mock_youtube_scraper.return_value.get_video_transcript.call_count == 2
    assert mock_store_embeddings.call_count == 2
    assert mock_redis_client.set.call_count == 2


def test_start_channel_processing_with_invalid_channel_id(
    mock_youtube_scraper,
    mock_pinecone,
    mock_celery_task,
    mock_transcript_exists,
    mock_store_embeddings,
    mock_redis_client
):
    # Mock YoutubeScraper to raise an exception when initialized with an invalid channel_id
    mock_youtube_scraper.side_effect = Exception("Invalid channel ID")

    # Test with invalid channel ID
    with pytest.raises(Exception, match="Invalid channel ID"):
        start_channel_processing(channel_id="INVALID_CHANNEL_ID", video_limit=2)
    mock_youtube_scraper.assert_called_once_with(channel_id="INVALID_CHANNEL_ID")
    mock_youtube_scraper.return_value.get_video_ids.assert_not_called()
    assert mock_store_embeddings.call_count == 0
    assert mock_redis_client.set.call_count == 0
