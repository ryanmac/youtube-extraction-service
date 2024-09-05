# app/services/channel_service.py
import logging
from urllib.request import urlopen
import json
import re
from datetime import timedelta
from app.core.config import settings
from app.core.celery_config import celery_app
from app.services.pinecone_service import index, generate_embedding

logger = logging.getLogger(__name__)


def extract_channel_name(url):
    pattern = r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/@([^\/\n?]+)"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def cached_api_call(cache_key, url, expiration_days=7):
    redis_client = celery_app.backend.client
    cached_data = redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    try:
        with urlopen(url) as response:
            data = json.load(response)
        redis_client.setex(cache_key, int(timedelta(days=expiration_days).total_seconds()), json.dumps(data))
        return data
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None


def get_channel_id(channel_name):
    query = '%20'.join(channel_name.split())
    search_url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=channel&key={settings.YOUTUBE_API_KEY}'
    logger.info(f"Fetching channel ID for {channel_name}")
    cache_key = f"channel_id:{channel_name}"
    data = cached_api_call(cache_key, search_url)
    if not data:
        return None

    channel_info = data.get("items", [])
    if not channel_info:
        return None

    channel_id = channel_info[0].get("id", {}).get("channelId")
    return channel_id


def build_url(channel_id, parts):
    parts_str = ','.join(parts)
    return f'https://www.googleapis.com/youtube/v3/channels?id={channel_id}&key={settings.YOUTUBE_API_KEY}&part={parts_str}'


def get_channel_metadata(channel_url_or_id):
    channel_name = extract_channel_name(channel_url_or_id)
    channel_id = get_channel_id(channel_name) if channel_name else channel_url_or_id

    if not channel_id:
        return None

    parts = ['snippet', 'statistics', 'topicDetails', 'status', 'brandingSettings', 'localizations']
    url = build_url(channel_id, parts)
    cache_key = f"channel_metadata:{channel_id}"
    data = cached_api_call(cache_key, url)

    if not data:
        return None

    return data.get("items", [])[0]


def store_channel_metadata(channel_metadata):
    redis_client = celery_app.backend.client
    channel_id = channel_metadata['id']
    expiration = timedelta(days=7)
    redis_client.setex(f"channel_metadata:{channel_id}", int(expiration.total_seconds()), json.dumps(channel_metadata))


def get_stored_channel_metadata(channel_id):
    redis_client = celery_app.backend.client
    metadata = redis_client.get(f"channel_metadata:{channel_id}")
    return json.loads(metadata) if metadata else None


def get_channel_info(channel_url_or_id):
    channel_name = extract_channel_name(channel_url_or_id)
    channel_id = get_channel_id(channel_name) if channel_name else channel_url_or_id

    if not channel_id:
        return None

    try:
        # Check for cached metadata
        metadata = get_stored_channel_metadata(channel_id)
        if not metadata:
            # If not cached, fetch and store
            metadata = get_channel_metadata(channel_id)
            if metadata:
                store_channel_metadata(metadata)
            else:
                return None

        # Query Pinecone for channel-specific information
        query_embedding = generate_embedding(channel_id)
        results = index.query(vector=query_embedding, filter={"channel_id": channel_id}, top_k=1, include_metadata=True)

        if not results['matches']:
            return {
                'channel_id': channel_id,
                'unique_video_count': 0,
                'total_embeddings': 0,
                'metadata': metadata
            }

        # Count unique video IDs and total embeddings
        unique_video_ids = set()
        total_embeddings = 0

        vector_count = index.describe_index_stats()['total_vector_count']
        results = index.query(vector=query_embedding, filter={"channel_id": channel_id}, top_k=vector_count, include_metadata=True)

        for match in results['matches']:
            video_id = match['metadata']['video_id']
            unique_video_ids.add(video_id)
            total_embeddings += 1

        return {
            'channel_id': channel_id,
            'unique_video_count': len(unique_video_ids),
            'total_embeddings': total_embeddings,
            'metadata': metadata
        }
    except Exception as e:
        logger.error(f"Error getting channel info: {str(e)}")
        return None
