# tests/e2e/test_channel_processing.py
import pytest
from fastapi import status
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_get_channel_info():
    with patch('app.services.channel_service.get_channel_info') as mock:
        yield mock


@pytest.fixture
def mock_youtube_scraper():
    with patch('app.services.youtube_scraper.YoutubeScraper') as mock:
        yield mock


@pytest.fixture
def mock_start_channel_processing():
    with patch('app.api.routes.start_channel_processing') as mock:
        yield mock


@pytest.fixture
def mock_transcript_exists():
    with patch('app.services.youtube_scraper.transcript_exists', return_value=False) as mock:
        yield mock


@pytest.fixture
def mock_celery_async_result():
    with patch('app.api.routes.celery_app.AsyncResult') as mock:
        yield mock


@pytest.fixture
def mock_pinecone():
    with patch('app.services.youtube_scraper.get_index_stats') as mock:
        yield mock


def test_fetch_channel_info(mock_get_channel_info, test_client):
    channel_url = "https://www.youtube.com/@drwaku"

    # Mock response for get_channel_info
    mock_get_channel_info.return_value = {
        "channel_id": "UCZf5IX90oe5gdPppMXGImwg",
        "unique_video_count": 2,
        "total_embeddings": 10,
        "metadata": {
            "id": "UCZf5IX90oe5gdPppMXGImwg",
            "snippet": {"title": "Dr Waku"}
        }
    }

    response = test_client.get(f"/channel_info?channel_url={channel_url}")
    assert response.status_code == status.HTTP_200_OK, "/channel_info failed"
    channel_info = response.json()
    assert "metadata" in channel_info, "Channel metadata not found"
    assert channel_info["channel_id"] == "UCZf5IX90oe5gdPppMXGImwg", "Channel ID mismatch"


def test_start_channel_processing(mock_start_channel_processing, mock_celery_async_result, test_client):
    channel_url = "https://www.youtube.com/@drwaku"

    # Mock Celery task
    mock_task = MagicMock()
    mock_task.id = "test_task_id"
    mock_start_channel_processing.apply_async.return_value = mock_task

    # Mock AsyncResult state
    mock_async_result = MagicMock()
    mock_async_result.state = "SUCCESS"
    mock_async_result.result = {"progress": 100, "channel_id": "UCZf5IX90oe5gdPppMXGImwg"}
    mock_celery_async_result.return_value = mock_async_result

    response = test_client.post("/process_channel", json={"channel_url": channel_url, "video_limit": 2})
    assert response.status_code == status.HTTP_200_OK, "/process_channel failed"
    job_id = response.json()["job_id"]
    assert job_id == "test_task_id", "Job ID mismatch"


def test_check_job_status(mock_celery_async_result, test_client):
    job_id = "test_task_id"

    # Mock AsyncResult state
    mock_async_result = MagicMock()
    mock_async_result.state = "SUCCESS"
    mock_async_result.result = {"progress": 100, "channel_id": "UCZf5IX90oe5gdPppMXGImwg"}
    mock_celery_async_result.return_value = mock_async_result

    response = test_client.get(f"/job_status/{job_id}")
    assert response.status_code == status.HTTP_200_OK, "/job_status failed"
    status_data = response.json()
    assert status_data["status"] == "SUCCESS", "Job did not complete successfully"
    assert status_data["channel_id"] == "UCZf5IX90oe5gdPppMXGImwg", "Channel ID mismatch"


def test_retrieve_relevant_chunks(mock_pinecone, test_client):
    channel_id = "UCZf5IX90oe5gdPppMXGImwg"
    query = "test query"

    # Mock channel existence in index
    mock_pinecone.return_value.Index.return_value.query.return_value = {
        "matches": [
            {
                "id": "video1_0",
                "score": 0.9,
                "metadata": {"text": "This is a test transcript.", "channel_id": "UCZf5IX90oe5gdPppMXGImwg"}
            }
        ]
    }

    response = test_client.get("/relevant_chunks", params={
        "query": query,
        "channel_id": channel_id,
        "chunk_limit": 5,
        "context_window": 1
    })

    assert response.status_code == status.HTTP_200_OK, "/relevant_chunks failed"
    chunks = response.json()["chunks"]
    assert len(chunks) > 0, "No relevant chunks were retrieved"
    assert "main_chunk" in chunks[0], "Main chunk key not found"
    assert isinstance(chunks[0]["main_chunk"], str), "Main chunk is not a string"
    assert len(chunks[0]["main_chunk"]) > 0, "Main chunk is empty"

    print(f"Actual main_chunk: {chunks[0]['main_chunk'][:100]}...")
