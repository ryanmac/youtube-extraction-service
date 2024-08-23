from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class ChannelRequest(BaseModel):
    channel_url: HttpUrl
    video_limit: Optional[int] = 5


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float = 0
    error: Optional[str] = None
    channel_id: Optional[str] = None


class ChunkMetadata(BaseModel):
    video_id: str
    channel_id: str
    chunk_index: int
    text: str


class RelevantChunk(BaseModel):
    main_chunk: str
    context_before: List[str]
    context_after: List[str]
    score: float


class RelevantChunksResponse(BaseModel):
    chunks: List[RelevantChunk]
