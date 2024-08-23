import logging
from celery import shared_task
from app.services.pinecone_service import store_embeddings
from app.core.config import settings
from typing import List
import tiktoken
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

openai.api_key = settings.OPENAI_API_KEY


@shared_task(bind=True)
def process_transcript(self, channel_id: str, video_id: str, transcript: str):
    try:
        chunks = split_into_chunks(transcript)
        embeddings = generate_embeddings(chunks)
        store_embeddings(channel_id, video_id, chunks, embeddings)
        self.update_state(state='SUCCESS', meta={'video_id': video_id})
    except Exception as e:
        logger.error(f"Error processing transcript for video {video_id}: {str(e)}")
        self.update_state(state='FAILURE', meta={'video_id': video_id, 'error': str(e)})
        raise


def split_into_chunks(text: str, max_tokens: int = settings.CHUNK_SIZE) -> List[str]:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks = []
    current_chunk = []
    current_chunk_tokens = 0

    for token in tokens:
        if current_chunk_tokens + 1 > max_tokens:
            chunks.append(encoding.decode(current_chunk))
            current_chunk = []
            current_chunk_tokens = 0
        current_chunk.append(token)
        current_chunk_tokens += 1

    if current_chunk:
        chunks.append(encoding.decode(current_chunk))

    return chunks


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_embeddings(chunks: List[str]) -> List[List[float]]:
    try:
        embeddings = []
        for chunk in chunks:
            response = openai.Embedding.create(
                input=chunk,
                model="text-embedding-ada-002"
            )
            embeddings.append(response['data'][0]['embedding'])
        return embeddings
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise
