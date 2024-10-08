# app/api/routes.py
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends
from app.models.schemas import ChannelRequest, JobStatus, RelevantChunksResponse, RelevantChunk, RecentChunksResponse, RecentChunk
from app.services.youtube_scraper import start_channel_processing
from app.core.celery_config import celery_app
from app.services.pinecone_service import retrieve_relevant_transcripts, retrieve_recent_chunks
from app.services.channel_service import get_channel_info as get_channel_info_service, get_channel_metadata, store_channel_metadata
from app.api.deps import get_api_key
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/channel_info")
async def channel_info(
    channel_id: Optional[str] = Query(None, description="Channel ID to search for, e.g., 'UC6vLzWN-3aFG8dgTgEOlx5g'"),
    channel_name: Optional[str] = Query(None, description="Channel name to search for, e.g., 'drwaku'"),
    channel_url: Optional[str] = Query(None, description="Channel URL to search for, e.g., 'https://www.youtube.com/@drwaku' or 'https://www.youtube.com/channel/@drwaku' or 'https://youtube.com/@drwaku'"),
    api_key: str = Depends(get_api_key)
):
    if not channel_id and not channel_name and not channel_url:
        raise HTTPException(status_code=400, detail="Please provide a channel ID, channel name, or channel URL")
    info = get_channel_info_service(
        channel_id=channel_id,
        channel_name=channel_name,
        channel_url=channel_url
    )
    if not info:
        logger.info(f"channel_id: {channel_id}")
        logger.info(f"channel_name: {channel_name}")
        logger.info(f"channel_url: {channel_url}")
        raise HTTPException(status_code=404, detail=f"Channel not found or no data available for {channel_url}")
    return info


@router.post("/refresh_channel_metadata")
async def refresh_channel_metadata(
    channel_id: Optional[str] = Query(None, description="Channel ID to refresh metadata for, e.g., 'UC6vLzWN-3aFG8dgTgEOlx5g'"),
    channel_name: Optional[str] = Query(None, description="Channel name to refresh metadata for, e.g., 'drwaku'"),
    channel_url: Optional[str] = Query(None, description="Channel URL to refresh metadata for, e.g., 'https://www.youtube.com/@drwaku' or 'https://www.youtube.com/channel/@drwaku' or 'https://youtube.com/@drwaku'"),
    api_key: str = Depends(get_api_key)
):
    if not channel_id and not channel_name and not channel_url:
        raise HTTPException(status_code=400, detail="Please provide a channel ID, channel name, or channel URL")
    try:
        logger.info(f"Refreshing metadata for channel: {channel_id}")
        metadata = get_channel_metadata(channel_id)
        if metadata is None:
            logger.error(f"Failed to fetch metadata for channel: {channel_id}")
            raise HTTPException(status_code=404, detail="Channel not found or unable to fetch metadata")
        if not metadata:
            logger.warning(f"No metadata found for channel: {channel_id}")
            return {"message": "No metadata available for this channel", "metadata": {}}
        logger.info(f"Successfully fetched metadata for channel: {channel_id}")
        store_channel_metadata(metadata)
        logger.info(f"Stored metadata for channel: {channel_id}")
        return {"message": "Channel metadata refreshed successfully", "metadata": metadata}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in refresh_channel_metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# TODO: add a check to see if the channel has been processed in the last 24 hours
# TODO: store the channel username in the index, not just the channel ID for faster lookups
@router.post("/process_channel", response_model=JobStatus)
async def process_channel(channel_request: ChannelRequest, api_key: str = Depends(get_api_key)):
    try:
        logger.info(f"Received request to process channel_id: {channel_request.channel_id} for {channel_request.video_limit} videos")
        job = start_channel_processing.apply_async(
            kwargs={
                'channel_id': str(channel_request.channel_id),
                'video_limit': channel_request.video_limit
            },
            queue='celery'
        )
        logger.info(f"Started channel processing job with ID: {job.id}")
        return JobStatus(job_id=job.id, status="STARTED")
    except Exception as e:
        logger.error(f"Error processing channel: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/job_status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, api_key: str = Depends(get_api_key)):
    try:
        job = celery_app.AsyncResult(job_id)
        logger.info(f"Job status for {job_id}: {job.state}")

        status = job.state
        if status == 'FAILURE':
            status = 'FAILED'

        result = job.result if isinstance(job.result, dict) else {}
        return JobStatus(
            job_id=job_id,
            status=status,
            progress=result.get('progress', 0) if status == 'SUCCESS' else 0,
            channel_id=result.get('channel_id'),
            error=str(job.result) if status == 'FAILED' else None
        )
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def monitor_job_progress(job_id: str):
    job = celery_app.AsyncResult(job_id)
    logger.info(f"Monitoring job progress for {job_id}")
    while job.state in ['PENDING', 'STARTED', 'PROGRESS']:
        logger.info(f"Job {job_id} is {job.state}")
        await asyncio.sleep(5)
        job = celery_app.AsyncResult(job_id)
    logger.info(f"Job {job_id} completed with status: {job.state}")
    return job.state


@router.get("/relevant_chunks", response_model=RelevantChunksResponse)
async def get_relevant_chunks(
    query: str = Query(..., description="The query to search for relevant chunks"),
    channel_id: str = Query(..., description="Channel ID to search in"),
    chunk_limit: int = Query(5, description="Number of top chunks to retrieve"),
    context_window: int = Query(1, description="Number of context chunks before and after the main chunk"),
    api_key: str = Depends(get_api_key)
):
    try:
        relevant_chunks = retrieve_relevant_transcripts(query, [channel_id], chunk_limit, context_window)
        return RelevantChunksResponse(chunks=[
            RelevantChunk(
                main_chunk=chunk['main_chunk'],
                context_before=chunk['context_before'],
                context_after=chunk['context_after'],
                score=chunk['score']
            ) for chunk in relevant_chunks
        ])
    except Exception as e:
        logger.error(f"Error retrieving relevant chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent_chunks", response_model=RecentChunksResponse)
async def get_recent_chunks(
    channel_id: str = Query(..., description="Channel ID to search in"),
    chunk_limit: int = Query(5, description="Number of recent chunks to retrieve"),
    api_key: str = Depends(get_api_key)
):
    try:
        recent_chunks = retrieve_recent_chunks(channel_id, chunk_limit)
        return RecentChunksResponse(chunks=[
            RecentChunk(
                video_id=chunk['video_id'],
                channel_id=chunk['channel_id'],
                chunk_index=chunk['chunk_index'],
                text=chunk['text']
            ) for chunk in recent_chunks
        ])
    except Exception as e:
        logger.error(f"Error retrieving recent chunks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
