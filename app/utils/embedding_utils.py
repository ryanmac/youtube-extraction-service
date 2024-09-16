# app/utils/embedding_utils.py
import logging
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from celery import Task
from openai import OpenAI
import time
from app.core.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    logger.info(f"Generating embedding for text: {text[:50]}...")
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        embedding = response.data[0].embedding
        logger.info(f"Generated embedding: {len(embedding)}")
        return embedding
    except AttributeError as e:
        logger.error(f"Unexpected response structure: {str(e)}")
        logger.error(f"Response: {response}")
        raise
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        if "api_key" in str(e).lower():
            logger.error("OpenAI API key may be invalid or not set")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_embeddings(chunks: List[str], task: Optional[Task] = None, model: str = "text-embedding-3-small") -> List[List[float]]:
    try:
        embeddings = []
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            embedding = generate_embedding(chunk, model)
            embeddings.append(embedding)

            if task:
                progress = (i / total_chunks) * 100
                task.update_state(state='PROGRESS', meta={'progress': progress})
                logger.info(f"Embedding progress: {progress:.2f}% ({i}/{total_chunks})")

            time.sleep(0.5)  # Rate limiting

        return embeddings
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise
