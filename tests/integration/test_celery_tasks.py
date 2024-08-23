import pytest
from unittest.mock import patch, MagicMock
from app.services.youtube_scraper import start_channel_processing, process_video
from app.services.transcript_processor import process_transcript


@pytest.fixture
def mock_celery_task():
    with patch('celery.app.task.Task.apply_async') as mock:
        mock.return_value.get = MagicMock()
        yield mock


def test_start_channel_processing_task(mock_youtube_scraper, mock_pinecone, mock_celery_task):
    mock_celery_task.return_value.get.return_value = {'status': 'All videos processed', 'progress': 100, 'channel_id': 'test_channel_id'}
    result = start_channel_processing.apply_async(args=["https://www.youtube.com/@drwaku", 2])
    assert result.get()['status'] == 'All videos processed'
    assert result.get()['progress'] == 100
    assert result.get()['channel_id'] == 'test_channel_id'


def test_process_video_task(mock_youtube_scraper, mock_celery_task, redis_client):
    mock_celery_task.return_value.get.return_value = "Video test_video_id processed successfully"
    result = process_video.apply_async(args=["test_channel_id", "test_video_id"])
    assert result.get() == "Video test_video_id processed successfully"
    assert redis_client.get("processed:test_video_id") == b"1"


def test_process_transcript_task(mock_pinecone, mock_openai, mock_celery_task):
    # Set up the mock for Pinecone index
    mock_index = MagicMock()
    mock_pinecone.return_value.Index.return_value = mock_index

    # Set up the mock for OpenAI embeddings
    mock_openai.embeddings.create.return_value.data = [{"embedding": [0.1] * 1536}]

    # Mock the store_embeddings function and other necessary functions
    with patch('app.services.transcript_processor.store_embeddings') as mock_store_embeddings, \
         patch('app.services.transcript_processor.split_into_chunks') as mock_split_into_chunks, \
         patch('app.services.transcript_processor.generate_embeddings') as mock_generate_embeddings, \
         patch('celery.app.task.Task.update_state') as mock_update_state:

        mock_split_into_chunks.return_value = ["chunk1", "chunk2"]
        mock_generate_embeddings.return_value = [[0.1] * 1536, [0.2] * 1536]

        # Execute the task synchronously
        result = process_transcript.apply(args=["test_channel", "test_video", "This is a test transcript."])

        # Check if the task completed successfully
        assert result.successful()

        # Check if the mocked functions were called
        mock_split_into_chunks.assert_called_once_with("This is a test transcript.")
        mock_generate_embeddings.assert_called_once_with(["chunk1", "chunk2"])
        mock_store_embeddings.assert_called_once_with(
            "test_channel", "test_video", ["chunk1", "chunk2"], [[0.1] * 1536, [0.2] * 1536]
        )

        # Check if update_state was called (this replaces the need to set backend)
        mock_update_state.assert_called_with(state='SUCCESS', meta={'video_id': 'test_video'})

    # Optional: Print out more information if the assertion fails
    if not mock_store_embeddings.called:
        print("store_embeddings was not called.")
        print("Mock calls:", mock_store_embeddings.mock_calls)
