# app/services/channel_service.py
import logging
from urllib.request import urlopen
import json
import re
from datetime import timedelta
from app.core.config import settings
from app.core.celery_config import celery_app
from app.services.pinecone_service import index, generate_embedding
from typing import Optional

logger = logging.getLogger(__name__)


def extract_channel_name(url):
    pattern = r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/(?:channel\/)?@([^\/\n?]+)"
    match = re.search(pattern, url)
    channel_name = match.group(1) if match else None
    logger.info(f"Extracted channel name: {channel_name}")
    return channel_name


def cached_api_call(cache_key, url, expiration_days=7):
    redis_client = celery_app.backend.client
    logger.info(f"Checking cache for key: {cache_key}")
    cached_data = redis_client.get(cache_key)
    if cached_data:
        logger.info(f"Using cached data for {url}")
        return json.loads(cached_data)
    logger.info(f"Fetching fresh data from {url}")
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
    search_url = f'https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&key={settings.YOUTUBE_API_KEY}'
    logger.info(f"Fetching channel ID for {channel_name} at URL: {search_url}")
    cache_key = f"channel_id::{channel_name}"
    data = cached_api_call(cache_key, search_url)
    if not data:
        return None

    channel_info = data if isinstance(data, list) else data.get("items", [])
    if not channel_info:
        return None

    logger.info(f"Found channel info for {channel_name}")
    logger.info(json.dumps(channel_info, indent=2))

    # Try to find a channel result first
    for item in channel_info:
        if item["id"].get("kind") == "youtube#channel":
            channel_id = item["id"]["channelId"]
            logger.info(f"Found channel ID: {channel_id}")
            return channel_id

    # If no channel found, use the first result's channelId
    if channel_info:
        channel_id = channel_info[0]["snippet"]["channelId"]
        logger.info(f"Using channelId from first result: {channel_id}")
        return channel_id

    logger.warning(f"No channel ID found for {channel_name}")
    return None


def build_url(channel_id, parts):
    parts_str = ','.join(parts)
    return f'https://www.googleapis.com/youtube/v3/channels?id={channel_id}&key={settings.YOUTUBE_API_KEY}&part={parts_str}'


def get_channel_metadata(channel_id: Optional[str] = None, channel_name: Optional[str] = None, channel_url: Optional[str] = None):
    if not channel_id:
        (channel_id, channel_name, channel_url) = get_channel_id_from_name_or_url(channel_name, channel_url)

    if not channel_id:
        logger.error(f"Channel not found: {channel_name or channel_url}")
        return None

    logger.info(f"Getting metadata for channel: {channel_id}")

    parts = ['snippet', 'statistics', 'topicDetails', 'status', 'brandingSettings', 'localizations']
    url = build_url(channel_id, parts)
    cache_key = f"channel_metadata:{channel_id}"
    data = cached_api_call(cache_key, url)

    items = data.get("items", [])
    if not items:
        logger.warning(f"No items found in channel metadata for channel ID: {channel_id}")
        return {}

    return items[0]


def store_channel_metadata(channel_metadata):
    logger.info(f"Storing metadata for channel: {channel_metadata['snippet']['title']}")
    redis_client = celery_app.backend.client
    channel_id = channel_metadata['id']
    expiration = timedelta(days=7)
    redis_client.setex(f"channel_metadata:{channel_id}", int(expiration.total_seconds()), json.dumps(channel_metadata))


def get_stored_channel_metadata(channel_id):
    logger.info(f"Getting stored metadata for channel: {channel_id}")
    redis_client = celery_app.backend.client
    metadata = redis_client.get(f"channel_metadata:{channel_id}")
    return json.loads(metadata) if metadata else None


def get_channel_id_from_name_or_url(channel_name: Optional[str] = None, channel_url: Optional[str] = None):
    if not channel_name and not channel_url:
        logger.error("No channel name or URL provided")
        return None, None, None

    if channel_name:
        channel_id = get_channel_id(channel_name)
    else:
        channel_name = extract_channel_name(channel_url)
        channel_id = get_channel_id(channel_name)

    return channel_id, channel_name, channel_url


def get_channel_info(channel_id: Optional[str] = None, channel_name: Optional[str] = None, channel_url: Optional[str] = None):
    if not channel_id and not channel_name and not channel_url:
        logger.error("No channel ID, channel name, or channel URL provided")
        return None

    if not channel_id:
        (channel_id, channel_name, channel_url) = get_channel_id_from_name_or_url(channel_name, channel_url)

    if not channel_id:
        logger.error(f"Channel not found: {channel_name or channel_url}")
        return None

    logger.info(f"Channel ID: {channel_id}")

    try:
        # Check for cached metadata
        metadata = get_stored_channel_metadata(channel_id)
        if not metadata:
            # If not cached, fetch and store
            logger.info(f"Fetching fresh metadata for channel: {channel_id}")
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
        results = index.query(vector=query_embedding, filter={"channel_id": channel_id}, top_k=min(vector_count, 10000), include_metadata=True)

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
