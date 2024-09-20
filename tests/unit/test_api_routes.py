import pytest
from fastapi import status
from unittest.mock import MagicMock, patch
from app.core.config import settings

YES_API_KEY = settings.YES_API_KEY


# Ensure all routes require API key
@pytest.mark.parametrize("endpoint,method,params", [
    ("/process_channel", "post", {"json": {"channel_url": "https://www.youtube.com/@drwaku"}}),
    ("/job_status/test_job_id", "get", {}),
    ("/relevant_chunks", "get", {"params": {"query": "test", "channel_id": "test_channel"}}),
    ("/recent_chunks", "get", {"params": {"channel_id": "test_channel"}}),
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


# Tests for channel_info endpoint
@pytest.mark.parametrize("channel_id,channel_name,channel_url,expected_status", [
    ("UC6vLzWN-3aFG8dgTgEOlx5g", None, None, status.HTTP_200_OK),
    (None, "drwaku", None, status.HTTP_200_OK),
    (None, None, "https://www.youtube.com/@drwaku", status.HTTP_200_OK),
    (None, None, None, status.HTTP_400_BAD_REQUEST)
])
def test_channel_info(test_client, mock_api_key_validation, api_key_header, channel_id, channel_name, channel_url, expected_status):
    params = {}
    if channel_id:
        params["channel_id"] = channel_id
    if channel_name:
        params["channel_name"] = channel_name
    if channel_url:
        params["channel_url"] = channel_url

    response = test_client.get("/channel_info", params=params, headers=api_key_header)
    assert response.status_code == expected_status


# Tests for process_channel endpoint
def test_process_channel(test_client, mock_celery, mock_api_key_validation, api_key_header):
    # Mock the `apply_async` method to return a mock with the required `id` attribute
    mock_task = MagicMock()
    mock_task.id = "test_job_id"
    mock_celery.apply_async.return_value = mock_task

    response = test_client.post("/process_channel", json={"channel_id": "UCZf5IX90oe5gdPppMXGImwg"}, headers=api_key_header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["job_id"] == "test_job_id"


# Tests for refresh_channel_metadata endpoint
@pytest.mark.parametrize("channel_id,expected_status", [
    ("UC6vLzWN-3aFG8dgTgEOlx5g", status.HTTP_200_OK),
    (None, status.HTTP_400_BAD_REQUEST)
])
def test_refresh_channel_metadata(test_client, mock_api_key_validation, api_key_header, channel_id, expected_status):
    params = {}
    if channel_id:
        params["channel_id"] = channel_id
    response = test_client.post("/refresh_channel_metadata", params=params, headers=api_key_header)
    assert response.status_code == expected_status


# Tests for get_job_status endpoint
@pytest.mark.parametrize("job_status,expected_status", [
    ("PENDING", "PENDING"),
    ("SUCCESS", "SUCCESS"),
    ("FAILURE", "FAILED"),
])
def test_get_job_status(test_client, mock_celery, job_status, expected_status, api_key_header):
    mock_async_result = MagicMock()
    mock_async_result.state = job_status
    mock_async_result.result = {"progress": 50, "channel_id": "UCZf5IX90oe5gdPppMXGImwg"} if job_status == "SUCCESS" else None
    mock_celery.AsyncResult.return_value = mock_async_result

    response = test_client.get("/job_status/test_job_id", headers=api_key_header)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == expected_status


# Tests for get_relevant_chunks endpoint
def test_get_relevant_chunks(test_client, mock_generate_embedding, mock_pinecone_query, api_key_header):
    response = test_client.get("/relevant_chunks", params={
        "query": "test query",
        "channel_id": "test_channel",
        "chunk_limit": 5,
        "context_window": 1
    }, headers=api_key_header)

    assert response.status_code == status.HTTP_200_OK
    assert "chunks" in response.json()

    chunks = response.json()["chunks"]
    assert len(chunks) > 0

    # Verify mocks were called correctly
    mock_generate_embedding.assert_called_once_with("test query")
    assert mock_pinecone_query.call_count == 2


# Tests for get_recent_chunks endpoint
def test_get_recent_chunks(test_client, mock_pinecone_query, api_key_header):
    response = test_client.get("/recent_chunks", params={
        "channel_id": "test_channel",
        "chunk_limit": 5
    }, headers=api_key_header)

    assert response.status_code == status.HTTP_200_OK
    assert "chunks" in response.json()

    chunks = response.json()["chunks"]
    assert len(chunks) > 0

    # Verify that the mocks were called
    assert mock_pinecone_query.call_count == 1
    first_call_args = mock_pinecone_query.call_args_list[0][1]
    assert first_call_args['filter'] == {'channel_id': {'$eq': 'test_channel'}}
