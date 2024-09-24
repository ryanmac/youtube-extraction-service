# app/services/youtube_scraper.py
import logging
from app.services.youtube_channel_scraper import YoutubeScraper
from app.services.transcript_processor import process_transcript, split_into_chunks
from app.utils.embedding_utils import generate_embeddings
from app.core.config import settings
import redis
from app.services.pinecone_service import transcript_exists, store_embeddings, get_index_stats
from app.core.celery_config import celery_app

redis_client = redis.Redis.from_url(settings.get_redis_url)
logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def start_channel_processing(self, channel_id: str, video_limit: int = 5):
    """
    Processes the videos from a specified YouTube channel by either using a channel ID or extracting it from a channel URL.
    """
    # Print out the arguments received for debugging
    logger.info(f"start_channel_processing received arguments: channel_id={channel_id}, video_limit={video_limit}")

    try:
        fy = YoutubeScraper(channel_id=channel_id)

        video_ids = fy.get_video_ids(limit=min(video_limit, settings.MAX_VIDEOS_PER_CHANNEL))
        logger.info(f"Found {len(video_ids)} videos")

        total_videos = len(video_ids)
        processed_videos = 0

        # Step 7: Process each video
        for video_id in video_ids:
            logger.info(f"Checking video {video_id}")
            if not transcript_exists(video_id):
                logger.info(f"Processing video {video_id}")
                transcript = fy.get_video_transcript(video_id=video_id)
                if transcript:
                    logger.info(f"Transcript found for video {video_id}")
                    chunks = split_into_chunks(transcript)
                    embeddings = generate_embeddings(chunks)
                    logger.info(f"Generated {len(embeddings)} embeddings for {len(chunks)} chunks")
                    store_embeddings(channel_id, video_id, chunks, embeddings)
                    redis_client.set(f"processed:{video_id}", "1")
                    logger.info(f"Embeddings stored for video {video_id}")
                else:
                    logger.warning(f"No transcript available for video {video_id}")
            else:
                logger.info(f"Video {video_id} already processed")

            # Step 8: Update progress
            processed_videos += 1
            progress = (processed_videos / total_videos) * 100
            self.update_state(state='PROGRESS', meta={'progress': progress})
            logger.info(f"Progress: {progress:.2f}%")

        # Step 9: Complete processing
        logger.info(f"Channel processing completed for {channel_id}")
        index_stats = get_index_stats()
        logger.info(f"Pinecone index stats after processing: {index_stats}")
        return {'status': 'All videos processed', 'progress': 100, 'channel_id': channel_id}

    except Exception as e:
        logger.error(f"Error processing channel {channel_id}: {str(e)}", exc_info=True)
        logger.error(f"Channel ID type: {type(channel_id)}, Video limit type: {type(video_limit)}")
        raise


@celery_app.task(bind=True)
def process_video(self, channel_id: str, video_id: str):
    if redis_client.get(f"processed:{video_id}"):
        return f"Video {video_id} already processed"

    try:
        logger.info(f"Processing video {video_id}")
        fy = YoutubeScraper(channel_id=channel_id)
        transcript = fy.get_video_transcript(video_id=video_id)
        process_transcript.delay(channel_id, video_id, transcript)
        redis_client.set(f"processed:{video_id}", "1")
        return f"Video {video_id} processed successfully"
    except Exception as e:
        logger.error(f"Error processing video {video_id}: {str(e)}")
        raise
