# app/services/pinecone_service.py
import logging
from pinecone import Pinecone
from app.core.config import settings
from app.utils.embedding_utils import generate_embedding
from typing import List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential
import json

pc = Pinecone(
    api_key=settings.PINECONE_API_KEY,
    environment=settings.PINECONE_ENVIRONMENT
)
index = pc.Index(settings.PINECONE_INDEX_NAME)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Pinecone logger to WARNING level
logging.getLogger("pinecone").setLevel(logging.WARNING)


def estimate_vector_size(vector_tuple):
    # Estimate the size of the vector tuple when serialized to JSON
    return len(json.dumps(vector_tuple).encode('utf-8'))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def store_embeddings(channel_id: str, video_id: str, chunks: List[str], embeddings: List[List[float]]):
    try:
        logger.info(f"Storing embeddings for video {video_id}: {len(chunks)} chunks, {len(embeddings)} embeddings")

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch in number of chunks ({len(chunks)}) and embeddings ({len(embeddings)})")

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
        def safe_upsert(vectors):
            try:
                index.upsert(vectors=vectors)
            except Exception as e:
                raise Exception(f"Failed to upsert vectors: {str(e)}")  # Raise a simpler, pickleable exception

        logger.info(f"Storing {len(chunks)} chunks and embeddings for video {video_id}")

        vectors = [
            (f"{video_id}_{i}", embedding, {
                "channel_id": channel_id,
                "video_id": video_id,
                "chunk_index": i,
                "text": chunk
            })
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        # Split into batches
        max_size = 1 * 1024 * 1024  # 1MB in bytes
        current_batch = []
        current_size = 0

        for vector in vectors:
            vector_size = estimate_vector_size(vector)

            if current_size + vector_size > max_size:
                logger.info(f"Upserting batch of size {len(current_batch)} (estimated {current_size/1024:.2f}KB) for video {video_id}")
                safe_upsert(current_batch)  # Call the safe retryable function
                current_batch = []
                current_size = 0

            current_batch.append(vector)
            current_size += vector_size

        if current_batch:
            logger.info(f"Upserting final batch of size {len(current_batch)} (estimated {current_size/1024:.2f}KB) for video {video_id}")
            safe_upsert(current_batch)

        logger.info(f"Successfully stored embeddings for video {video_id}")

    except Exception as e:
        logger.error(f"Error storing embeddings for video {video_id}: {str(e)}")
        logger.error(f"channel_id type: {type(channel_id)}, video_id type: {type(video_id)}, "
                     f"chunks type: {type(chunks)}, embeddings type: {type(embeddings)}")
        raise Exception(f"Error storing embeddings: {str(e)}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def retrieve_embeddings(query_embedding: List[float], top_k: int = 5):
    try:
        results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
        return results
    except Exception as e:
        # Log the error here
        logger.error(f"Error retrieving embeddings: {str(e)}")
        raise


def log_embedding(embedding: List[float], prefix: str = ""):
    pass
    # if len(embedding) > 4:
    #     logger.info(f"{prefix}Embedding (first 2 and last 2 dimensions): {embedding[:2]} ... {embedding[-2:]}")
    # else:
    #     logger.info(f"{prefix}Embedding: {embedding}")


def split_into_chunks(text: str, token_limit: int = 200) -> List[str]:
    words = text.split()
    chunks = []
    current_chunk = []
    current_token_count = 0

    for word in words:
        word_token_count = len(word) // 4 + 1  # Rough estimate of token count
        if current_token_count + word_token_count > token_limit:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_token_count = word_token_count
        else:
            current_chunk.append(word)
            current_token_count += word_token_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def transcript_exists(video_id: str) -> bool:
    results = index.fetch([f"{video_id}_0"])
    return len(results['vectors']) > 0


def get_index_stats():
    try:
        stats = index.describe_index_stats()
        logger.info(f"Pinecone index stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error getting index stats: {str(e)}")
        return None


def is_index_empty():
    stats = get_index_stats()
    return stats['total_vector_count'] == 0 if stats else True


def retrieve_relevant_transcripts(query: str, channel_ids: List[str], limit: int = 5, context_window: int = 1) -> List[Dict]:
    try:
        logger.info(f"Generating embedding for query: {query}")
        query_embedding = generate_embedding(query)
        logger.info(f"Generated query embedding with length: {len(query_embedding)}")

        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []

        if channel_ids:
            existing_channels = [channel_id for channel_id in channel_ids if channel_exists_in_index(channel_id)]
            if not existing_channels:
                logger.warning(f"None of the provided channel IDs exist in the index: {channel_ids}")
                return []
            filter_dict = {"channel_id": {"$in": existing_channels}}
        else:
            filter_dict = None

        logger.info(f"Using filter: {filter_dict}")

        results = index.query(
            vector=query_embedding,
            filter=filter_dict,
            top_k=limit,
            include_metadata=True
        )

        logger.info(f"Query returned {len(results['matches'])} results")

        relevant_chunks = []
        for match in results['matches']:
            chunk_index = int(match['id'].split('_')[-1])
            video_id = '_'.join(match['id'].split('_')[:-1])

            main_chunk = match['metadata'].get('text', match['metadata'].get('transcript_chunk', ''))

            context_before = []
            context_after = []

            for i in range(1, context_window + 1):
                before_id = f"{video_id}_{chunk_index - i}"
                after_id = f"{video_id}_{chunk_index + i}"

                before_result = index.fetch(ids=[before_id])
                after_result = index.fetch(ids=[after_id])

                if before_result['vectors']:
                    context_before.insert(0, before_result['vectors'][before_id]['metadata'].get('text', before_result['vectors'][before_id]['metadata'].get('transcript_chunk', '')))
                if after_result['vectors']:
                    context_after.append(after_result['vectors'][after_id]['metadata'].get('text', after_result['vectors'][after_id]['metadata'].get('transcript_chunk', '')))

            relevant_chunks.append({
                "main_chunk": main_chunk,
                "context_before": context_before,
                "context_after": context_after,
                "score": match['score']
            })

        logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks")
        return relevant_chunks
    except Exception as e:
        logger.error(f"Error retrieving relevant transcripts: {str(e)}")
        return []


def retrieve_recent_chunks(channel_id: str, limit: int = 5) -> List[Dict]:
    try:
        results = index.query(
            vector=[0] * 1536,  # Dummy vector
            filter={"channel_id": {"$eq": channel_id}},
            top_k=limit,
            include_metadata=True
        )

        recent_chunks = []
        for match in results['matches']:
            video_id = match['metadata']['video_id']
            chunk_index = match['metadata']['chunk_index']
            text = match['metadata'].get('text', match['metadata'].get('transcript_chunk', ''))
            recent_chunks.append({
                "video_id": video_id,
                "channel_id": channel_id,
                "chunk_index": chunk_index,
                "text": text
            })

        logger.info(f"Retrieved {len(recent_chunks)} recent chunks for channel {channel_id}")
        return recent_chunks
    except Exception as e:
        logger.error(f"Error retrieving recent chunks: {str(e)}")
        return []


def inspect_index_contents(limit: int = 10):
    try:
        # Fetch a sample of vectors from the index
        sample_query = index.query(
            vector=[0] * 1536,  # Assuming 1536-dimensional embeddings
            top_k=limit,
            include_metadata=True
        )

        logger.info(f"Sample of {len(sample_query['matches'])} vectors from the index:")
        for match in sample_query['matches']:
            logger.info(f"ID: {match['id']}")
            logger.info(f"Metadata: {match['metadata']}")
            logger.info(f"Score: {match['score']}")
            logger.info("---")

        return sample_query['matches']
    except Exception as e:
        logger.error(f"Error inspecting index contents: {str(e)}")
        return []


def direct_pinecone_query(query: str, top_k: int = 5):
    try:
        query_embedding = generate_embedding(query)
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        logger.info(f"Direct Pinecone query reults: {len(results['matches'])}")
        # logger.info(f"Direct Pinecone query results: {results}")
        return results
    except Exception as e:
        logger.error(f"Error in direct Pinecone query: {str(e)}")
        return None


def inspect_stored_vectors(limit: int = 10):
    try:
        # Fetch a sample of vectors from the index
        sample_query = index.query(
            vector=[0] * 1536,  # Assuming 1536-dimensional embeddings
            top_k=limit,
            include_metadata=True
        )

        logger.info(f"Sample of {len(sample_query['matches'])} vectors from the index:")
        for match in sample_query['matches'][:2]:
            logger.info(f"ID: {match['id']}")
            logger.info(f"Metadata: {match['metadata']}")
            logger.info(f"Score: {match['score']}")
            logger.info("---")

        return sample_query['matches']
    except Exception as e:
        logger.error(f"Error inspecting stored vectors: {str(e)}")
        return []


def channel_exists_in_index(channel_id: str) -> bool:
    try:
        results = index.query(
            vector=[0] * 1536,  # Dummy vector
            filter={"channel_id": {"$eq": channel_id}},
            top_k=1,
            include_metadata=True
        )
        exists = len(results['matches']) > 0
        logger.info(f"Channel {channel_id} exists in index: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking if channel exists: {str(e)}")
        return False
