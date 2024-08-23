import pytest
from app.services.youtube_scraper import start_channel_processing
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_celery_task():
    with patch('celery.app.task.Task.update_state') as mock:
        yield mock


def test_start_channel_processing(mock_youtube_scraper, mock_pinecone, mock_celery_task):
    mock_youtube_scraper.return_value.get_channel_id.return_value = "test_channel_id"
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"

    mock_index = MagicMock()
    mock_pinecone.return_value.Index.return_value = mock_index

    result = start_channel_processing("https://www.youtube.com/@drwaku", 2)

    assert result == {'status': 'All videos processed', 'progress': 100, 'channel_id': 'test_channel_id'}
    mock_youtube_scraper.return_value.get_channel_id.assert_called_once()
    mock_youtube_scraper.return_value.get_video_ids.assert_called_once()
    assert mock_youtube_scraper.return_value.get_video
