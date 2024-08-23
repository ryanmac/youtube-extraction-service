import pytest
from fastapi import status
import time


def test_end_to_end_channel_processing(test_client, mock_youtube_scraper, mock_pinecone):
    channel_url = "https://www.youtube.com/@drwaku"

    # Start channel processing
    response = test_client.post("/process_channel", json={"channel_url": channel_url})
    assert response.status_code == status.HTTP_200_OK
    job_id = response.json()["job_id"]

    # Mock successful job completion
    mock_youtube_scraper.return_value.get_channel_id.return_value = "test_channel_id"
    mock_youtube_scraper.return_value.get_video_ids.return_value = ["video1", "video2"]
    mock_youtube_scraper.return_value.get_video_transcript.return_value = "Test transcript"

    # Wait for the job to complete
    timeout = 60  # 1 minute
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            pytest.fail("Job did not complete within the timeout period")

        response = test_client.get(f"/job_status/{job_id}")
        assert response.status_code == status.HTTP_200_OK
        status_data = response.json()

        if status_data["status"] == "SUCCESS":
            break
        elif status_data["status"] == "FAILED":
            pytest.fail(f"Job failed: {status_data.get('error')}")

        time.sleep(1)

    # Verify that the channel was processed
    channel_id = status_data.get("channel_id")
    assert channel_id is not None, "Channel ID was not returned in the job result"

    # Mock channel existence in index
    mock_pinecone.return_value.Index.return_value.query.return_value = {"matches": [{"id": "video1_0"}]}

    # Test retrieval of relevant chunks
    query = "test query"
    response = test_client.get("/relevant_chunks", params={
        "query": query,
        "channel_id": channel_id,
        "chunk_limit": 5,
        "context_window": 1
    })

    assert response.status_code == status.HTTP_200_OK
    chunks = response.json()["chunks"]
    assert len(chunks) > 0, "No relevant chunks were retrieved"
    assert len(chunks[0]["main_chunk"]) > 0, "Main chunk is empty"
