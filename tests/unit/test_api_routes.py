import pytest
from fastapi import status
from unittest.mock import MagicMock, patch
from app.core.config import settings

YES_API_KEY = settings.YES_API_KEY


@pytest.mark.parametrize("endpoint,method,params", [
    ("/process_channel", "post", {"json": {"channel_url": "https://www.youtube.com/@drwaku"}}),
    ("/job_status/test_job_id", "get", {}),
    ("/relevant_chunks", "get", {"params": {"query": "test", "channel_id": "test_channel"}}),
    ("/channel_info", "get", {"params": {"channel_url": "https://www.youtube.com/@drwaku"}}),
    ("/refresh_channel_metadata", "post", {"params": {"channel_url": "https://www.youtube.com/@drwaku"}})
])
def test_endpoints_require_api_key(test_client, endpoint, method, params):
    client_method = getattr(test_client, method)
    response = client_method(endpoint, **params, headers={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Missing API Key"


@pytest.fixture
def mock_api_key_validation():
    with patch("app.api.deps.get_api_key", return_value=YES_API_KEY):
        yield


def test_process_channel(test_client, mock_celery, mock_api_key_validation, api_key_header):
    mock_celery.send_task.return_value.id = "test_job_id"

    response = test_client.post("/process_channel", json={"channel_url": "https://www.youtube.com/@drwaku"}, headers=api_key_header)

    assert response.status_code == status.HTTP_200_OK
    assert "job_id" in response.json()
    assert isinstance(response.json()["job_id"], str) and response.json()["job_id"]


def test_process_channel_with_valid_api_key(test_client, mock_celery, mock_api_key_validation, api_key_header):
    mock_celery.send_task.return_value.id = "test_job_id"

    response = test_client.post(
        "/process_channel",
        json={"channel_url": "https://www.youtube.com/@drwaku"},
        headers=api_key_header
    )

    assert response.status_code == status.HTTP_200_OK
    assert "job_id" in response.json()
    assert isinstance(response.json()["job_id"], str) and response.json()["job_id"]


@pytest.mark.parametrize("job_status,expected_status", [
    ("PENDING", "PENDING"),
    ("SUCCESS", "SUCCESS"),
    ("FAILURE", "FAILED"),
])
def test_get_job_status(test_client, mock_celery, job_status, expected_status, api_key_header):
    mock_async_result = MagicMock()
    mock_async_result.state = job_status
    mock_async_result.result = {"progress": 50, "channel_id": "drwaku"} if job_status == "SUCCESS" else None
    mock_celery.AsyncResult.return_value = mock_async_result

    response = test_client.get("/job_status/test_job_id", headers=api_key_header)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] in ["PENDING", "SUCCESS", "FAILED"]


def test_get_relevant_chunks(test_client, mock_pinecone, mock_openai, api_key_header):
    mock_index = mock_pinecone.return_value.Index.return_value
    mock_index.query.return_value = {
        "matches": [
            {
                "id": "video1_0",
                "score": 0.9,
                "metadata": {"text": "This is a test transcript.", "channel_id": "drwaku"}
            }
        ]
    }
    mock_openai.embeddings.create.return_value.data = [{"embedding": [0.1] * 1536}]

    response = test_client.get("/relevant_chunks", params={
        "query": "test query",
        "channel_id": "test_channel",
        "chunk_limit": 5,
        "context_window": 1
    }, headers=api_key_header)

    assert response.status_code == status.HTTP_200_OK
    assert "chunks" in response.json()
    assert len(response.json()["chunks"]) == 1
    assert len(response.json()["chunks"][0]["main_chunk"]) > 0
    assert response.json()["chunks"][0]["main_chunk"] == "This is a test transcript."
