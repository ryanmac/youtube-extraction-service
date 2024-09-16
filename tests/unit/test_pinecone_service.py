# tests/unit/test_pinecone_service.py
import pytest
from app.utils.embedding_utils import generate_embedding
from unittest.mock import MagicMock


@pytest.fixture
def mock_pinecone(mocker):
    mock = mocker.patch('app.services.pinecone_service.Pinecone')
    mock_index = MagicMock()
    mock.return_value.Index.return_value = mock_index
    return mock_index


@pytest.fixture
def mock_openai(mocker):
    return mocker.patch('app.utils.embedding_utils.client.embeddings.create')


# def test_store_embeddings(mock_pinecone, mock_openai):
#     mock_openai.return_value.data = [MagicMock(embedding=[0.1] * 1536)]

#     channel_id = "test_channel"
#     video_id = "test_video"
#     transcript = "This is a test transcript."

#     store_embeddings(channel_id, video_id, transcript)

#     mock_pinecone.upsert.assert_called_once()
#     call_args = mock_pinecone.upsert.call_args[1]
#     assert "vectors" in call_args
#     assert len(call_args["vectors"]) > 0
#     assert call_args["vectors"][0][0].startswith(f"{video_id}_")


# def test_retrieve_relevant_transcripts(mock_pinecone, mock_openai, mocker):
#     mock_openai.return_value.data = [MagicMock(embedding=[0.1] * 1536)]
#     mocker.patch('app.services.pinecone_service.channel_exists_in_index', return_value=True)

#     mock_pinecone.query.return_value = {
#         "matches": [
#             {
#                 "id": "video1_0",
#                 "score": 0.9,
#                 "metadata": {"text": "Relevant chunk 1", "channel_id": "test_channel"}
#             },
#             {
#                 "id": "video2_0",
#                 "score": 0.8,
#                 "metadata": {"text": "Relevant chunk 2", "channel_id": "test_channel"}
#             }
#         ]
#     }

#     query = "test query"
#     channel_ids = ["test_channel"]
#     results = retrieve_relevant_transcripts(query, channel_ids)

#     assert len(results) == 2
#     assert results[0]["main_chunk"] == "Relevant chunk 1"
#     assert results[1]["main_chunk"] == "Relevant chunk 2"


def test_generate_embedding(mock_openai):
    mock_openai.return_value.data = [MagicMock(embedding=[0.1] * 1536)]

    text = "Test text"
    embedding = generate_embedding(text)

    assert len(embedding) == 1536
    mock_openai.assert_called_once_with(input=text, model="text-embedding-3-small")


# @pytest.mark.parametrize("channel_id,expected", [
#     ("existing_channel", True),
#     ("non_existing_channel", False)
# ])
# def test_channel_exists_in_index(mock_pinecone, channel_id, expected):
#     mock_pinecone.query.return_value = {
#         "matches": [{"id": "video1_0"}] if expected else []
#     }

#     result = channel_exists_in_index(channel_id)

#     assert result == expected
#     mock_pinecone.query.assert_called_once()
