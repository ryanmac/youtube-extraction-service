# app/services/youtube_scraper.py
import logging
# from celery import shared_task
from yt_channel_scraper import YoutubeScraper
from app.services.transcript_processor import process_transcript
from app.core.config import settings
import redis
# from tenacity import retry, stop_after_attempt, wait_exponential
from app.services.pinecone_service import transcript_exists, store_embeddings, get_index_stats
from app.core.celery_config import celery_app
from app.services.channel_service import get_channel_info
import json

redis_client = redis.Redis.from_url(settings.REDIS_URL)
logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def start_channel_processing(self, channel_url: str, video_limit: int = 5):
    try:
        # Extract channel name or ID from URL
        channel_name_or_id = channel_url.split('/')[-1]

        # Fetch and store channel metadata
        channel_info = get_channel_info(channel_name_or_id)
        print(json.dumps(channel_info, indent=2))
        if not channel_info:
            raise Exception(f"Channel metadata not found for {channel_name_or_id}")
        channel_id = channel_info.get('channel_id')
        if not channel_id:
            raise Exception(f"Channel ID not found in channel info for {channel_name_or_id}")

        logger.info(f"Starting channel processing for {channel_url} with id {channel_id}")
        fy = YoutubeScraper(url=channel_url)
        logger.info(f"Channel ID: {channel_id}")
        video_ids = fy.get_video_ids(limit=max(video_limit, settings.MAX_VIDEOS_PER_CHANNEL))
        logger.info(f"Found {len(video_ids)} videos")

        total_videos = len(video_ids)
        processed_videos = 0

        for video_id in video_ids:
            logger.info(f"Checking video {video_id}")
            if not transcript_exists(video_id):
                logger.info(f"Processing video {video_id}")
                transcript = fy.get_video_transcript(video_id=video_id)
                if transcript:
                    logger.info(f"Transcript found for video {video_id}")
                    store_embeddings(channel_id, video_id, transcript)
                    redis_client.set(f"processed:{video_id}", "1")
                    logger.info(f"Embeddings stored for video {video_id}")
                else:
                    logger.warning(f"No transcript available for video {video_id}")
            else:
                logger.info(f"Video {video_id} already processed")

            processed_videos += 1
            progress = (processed_videos / total_videos) * 100
            self.update_state(state='PROGRESS', meta={'progress': progress})
            logger.info(f"Progress: {progress:.2f}%")

        logger.info(f"Channel processing completed for {channel_url}")
        index_stats = get_index_stats()
        logger.info(f"Pinecone index stats after processing: {index_stats}")
        return {'status': 'All videos processed', 'progress': 100, 'channel_id': channel_id}
    except Exception as e:
        logger.error(f"Error processing channel {channel_url}: {str(e)}")
        raise


@celery_app.task(bind=True)
def process_video(self, channel_id: str, video_id: str):
    if redis_client.get(f"processed:{video_id}"):
        return f"Video {video_id} already processed"

    try:
        logger.info(f"Processing video {video_id}")
        fy = YoutubeScraper()
        transcript = fy.get_video_transcript(video_id=video_id)
        process_transcript.delay(channel_id, video_id, transcript)
        redis_client.set(f"processed:{video_id}", "1")
        return f"Video {video_id} processed successfully"
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {str(e)}")
        raise
