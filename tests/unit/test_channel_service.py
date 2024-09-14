# tests/unit/test_channel_service.py
import pytest
from unittest.mock import patch
from app.services.channel_service import (
    extract_channel_name,
    get_channel_id,
    get_channel_metadata,
    get_channel_info,
    cached_api_call
)


@pytest.fixture
def mock_redis_client():
    with patch('app.services.channel_service.celery_app.backend.client') as mock:
        yield mock


@pytest.fixture
def mock_urlopen():
    with patch('app.services.channel_service.urlopen') as mock:
        yield mock


@pytest.fixture
def mock_pinecone_index():
    with patch('app.services.channel_service.index') as mock:
        yield mock


@pytest.fixture
def mock_generate_embedding():
    with patch('app.services.channel_service.generate_embedding') as mock:
        yield mock


def test_extract_channel_name():
    assert extract_channel_name("https://www.youtube.com/@drwaku") == "drwaku"
    assert extract_channel_name("https://youtube.com/@channel123") == "channel123"
    assert extract_channel_name("invalid_url") is None


def test_get_channel_id(mock_redis_client, mock_urlopen):
    mock_redis_client.get.return_value = None
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b'''
    {
        "items": [
            {
                "id": {
                    "channelId": "UCZf5IX90oe5gdPppMXGImwg"
                }
            }
        ]
    }
    '''

    channel_id = get_channel_id("drwaku")
    assert channel_id == "UCZf5IX90oe5gdPppMXGImwg"


def test_get_channel_metadata(mock_redis_client, mock_urlopen):
    mock_redis_client.get.return_value = None
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b'''
    {
        "items": [
            {
                "id": "UCZf5IX90oe5gdPppMXGImwg",
                "snippet": {
                    "title": "Dr. Waku"
                }
            }
        ]
    }
    '''

    metadata = get_channel_metadata("UCZf5IX90oe5gdPppMXGImwg")
    assert metadata["id"] == "UCZf5IX90oe5gdPppMXGImwg"
    assert metadata["snippet"]["title"] == "Dr. Waku"


def test_get_channel_info(mock_redis_client, mock_urlopen, mock_pinecone_index, mock_generate_embedding):
    mock_redis_client.get.return_value = None
    mock_urlopen.return_value.__enter__.return_value.read.return_value = b'''
    {
        "items": [
            {
                "id": {
                    "kind": "youtube#channel",
                    "channelId": "UCZf5IX90oe5gdPppMXGImwg"
                },
                "snippet": {
                    "title": "Dr. Waku"
                }
            }
        ]
    }
    '''
    mock_generate_embedding.return_value = [0.1] * 1536
    mock_pinecone_index.query.return_value = {
        "matches": [
            {"metadata": {"video_id": "video1"}},
            {"metadata": {"video_id": "video2"}},
            {"metadata": {"video_id": "video1"}}
        ]
    }
    mock_pinecone_index.describe_index_stats.return_value = {"total_vector_count": 3}

    channel_info = get_channel_info(channel_url="https://www.youtube.com/@drwaku")
    assert channel_info["channel_id"] == "UCZf5IX90oe5gdPppMXGImwg"
    assert channel_info["unique_video_count"] == 2
    assert channel_info["total_embeddings"] == 3
    assert channel_info["metadata"]["snippet"]["title"] == "Dr. Waku"


@pytest.mark.parametrize("cache_hit", [True, False])
def test_cached_api_call(mock_redis_client, mock_urlopen, cache_hit):
    cache_key = "test_key"
    url = "https://api.example.com/data"

    if cache_hit:
        mock_redis_client.get.return_value = b'{"cached": "data"}'
        result = cached_api_call(cache_key, url)
        assert result == {"cached": "data"}
        mock_urlopen.assert_not_called()
    else:
        mock_redis_client.get.return_value = None
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"fresh": "data"}'
        result = cached_api_call(cache_key, url)
        assert result == {"fresh": "data"}
        mock_urlopen.assert_called_once_with(url)
        mock_redis_client.setex.assert_called_once()
