# tests/unit/test_transcript_processor.py
import pytest
from app.services.transcript_processor import process_transcript, split_into_chunks
from unittest.mock import patch


@pytest.fixture
def test_split_into_chunks():
    text = "This is a test transcript. It contains multiple sentences to ensure proper chunking."
    chunks = split_into_chunks(text, max_tokens=10)
    assert len(chunks) > 1
    assert all(len(chunk.split()) <= 10 for chunk in chunks)


@patch('app.services.transcript_processor.store_embeddings')
@patch('app.services.transcript_processor.generate_embeddings')
def test_process_transcript(mock_generate_embeddings, mock_store_embeddings):
    mock_generate_embeddings.return_value = [[0.1] * 1536]  # Mocking the generated embeddings

    with patch('celery.app.task.Task.update_state') as mock_update_state:
        result = process_transcript("test_channel", "test_video", "This is a test transcript.")

    mock_generate_embeddings.assert_called_once()
    mock_store_embeddings.assert_called_once()
    mock_update_state.assert_called_with(state='SUCCESS', meta={'video_id': 'test_video'})
    assert result == {'status': 'success', 'video_id': 'test_video'}


@patch('app.services.transcript_processor.store_embeddings')
@patch('app.services.transcript_processor.generate_embeddings')
def test_process_transcript_with_error(mock_generate_embeddings, mock_store_embeddings):
    mock_generate_embeddings.side_effect = Exception("Embedding generation failed")

    with patch('celery.app.task.Task.update_state') as mock_update_state:
        result = process_transcript("test_channel", "test_video", "This is a test transcript.")

    mock_generate_embeddings.assert_called_once()
    mock_store_embeddings.assert_not_called()
    mock_update_state.assert_called_with(state='FAILURE', meta={'video_id': 'test_video', 'error': 'Embedding generation failed'})
    assert result == {'status': 'failure', 'video_id': 'test_video', 'error': 'Embedding generation failed'}
