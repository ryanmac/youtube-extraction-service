# app/services/transcript_processor.py
import logging
from celery import shared_task, Task
from app.services.pinecone_service import store_embeddings
from app.utils.embedding_utils import generate_embeddings
from app.core.config import settings
from typing import List, Union
import tiktoken
import openai

logger = logging.getLogger(__name__)

openai.api_key = settings.OPENAI_API_KEY


@shared_task(bind=True)
def process_transcript(self_or_task: Union[Task, str], channel_id: str, video_id: str, transcript: str):
    try:
        chunks = split_into_chunks(transcript)
        task = self_or_task if isinstance(self_or_task, Task) else None
        embeddings = generate_embeddings(chunks, task=task)
        store_embeddings(channel_id, video_id, chunks, embeddings)
        if isinstance(self_or_task, Task):
            self_or_task.update_state(state='SUCCESS', meta={'video_id': video_id})
        return {'status': 'success', 'video_id': video_id}
    except Exception as e:
        logger.error(f"Error processing transcript for video {video_id}: {str(e)}")
        if isinstance(self_or_task, Task):
            self_or_task.update_state(state='FAILURE', meta={'video_id': video_id, 'error': str(e)})
        return {'status': 'failure', 'video_id': video_id, 'error': str(e)}


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
