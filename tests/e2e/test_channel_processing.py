# tests/e2e/test_channel_processing.py
from fastapi import status
from unittest.mock import patch, MagicMock


@patch('app.services.youtube_scraper.YoutubeScraper')
@patch('app.services.channel_service.get_channel_info')
@patch('app.services.youtube_scraper.transcript_exists', return_value=False)
@patch('app.api.routes.start_channel_processing')  # Add this line
def test_end_to_end_channel_processing(mock_start_channel_processing, mock_transcript_exists, mock_get_channel_info, mock_youtube_scraper, test_client, mock_pinecone):
    channel_url = "https://www.youtube.com/@drwaku"

    # Mock get_channel_info (from test_channel_service.py)
    mock_get_channel_info.return_value = {
        "channel_id": "UCZf5IX90oe5gdPppMXGImwg",
        "unique_video_count": 2,
        "total_embeddings": 10,
        "metadata": {
            "id": "UCZf5IX90oe5gdPppMXGImwg",
            "snippet": {"title": "Dr Waku"}
        }
    }

    # Mock YoutubeScraper (from test_youtube_scraper.py)
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"

    # Mock Celery task
    mock_task = MagicMock()
    mock_task.id = "test_task_id"
    mock_start_channel_processing.apply_async.return_value = mock_task

    # Mock AsyncResult
    mock_async_result = MagicMock()
    mock_async_result.state = "SUCCESS"
    mock_async_result.result = {"progress": 100, "channel_id": "UCZf5IX90oe5gdPppMXGImwg"}

    with patch('app.api.routes.celery_app.AsyncResult', return_value=mock_async_result):
        # Check if channel exists and fetch metadata
        response = test_client.get(f"/channel_info?channel_url={channel_url}")
        assert response.status_code == status.HTTP_200_OK, "/channel_info failed"
        channel_info = response.json()
        assert "metadata" in channel_info, "Channel metadata not found"
        channel_id = channel_info["channel_id"]

        # Start channel processing
        response = test_client.post("/process_channel", json={"channel_url": channel_url, "video_limit": 2})
        assert response.status_code == status.HTTP_200_OK, "/process_channel failed"
        job_id = response.json()["job_id"]
        assert job_id == "test_task_id", "Job ID mismatch"

        # Check job status (should be immediate due to our mock)
        response = test_client.get(f"/job_status/{job_id}")
        assert response.status_code == status.HTTP_200_OK, "/job_status failed"
        status_data = response.json()

        assert status_data["status"] == "SUCCESS", "Job did not complete successfully"
        assert status_data["channel_id"] == "UCZf5IX90oe5gdPppMXGImwg", "Channel ID mismatch"

        # Mock channel existence in index (from test_api_routes.py)
        mock_pinecone.return_value.Index.return_value.query.return_value = {
            "matches": [
                {
                    "id": "video1_0",
                    "score": 0.9,
                    "metadata": {"text": "This is a test transcript.", "channel_id": "UCZf5IX90oe5gdPppMXGImwg"}
                }
            ]
        }

        # Test retrieval of relevant chunks
        query = "test query"
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
