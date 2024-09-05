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


# def test_generate_embeddings(mock_openai):
#     mock_openai.embeddings.create.return_value.data = [{"embedding": [0.1] * 1536}]
#     chunks = ["This is chunk 1", "This is chunk 2"]
#     embeddings = generate_embeddings(chunks)
#     assert len(embeddings) == 2
#     assert all(len(embedding) == 1536 for embedding in embeddings)
#     assert mock_openai.embeddings.create.call_count == 2


@patch('app.services.transcript_processor.store_embeddings')
def test_process_transcript(mock_store_embeddings, mock_openai):
    mock_openai.embeddings.create.return_value.data = [{"embedding": [0.1] * 1536}]

    with patch('celery.app.task.Task.update_state') as mock_update_state:
        process_transcript("test_channel", "test_video", "This is a test transcript.")

    mock_store_embeddings.assert_called_once()
    mock_update_state.assert_called_with(state='SUCCESS', meta={'video_id': 'test_video'})
