# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "YouTube Extraction Service"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None
    PINECONE_API_KEY: str
    PINECONE_ENVIRONMENT: str
    PINECONE_INDEX_NAME: str
    MAX_VIDEOS_PER_CHANNEL: int = 1000
    CHUNK_SIZE: int = 200
    OPENAI_API_KEY: Optional[str] = None
    PINECONE_HOST: Optional[str] = None
    PINECONE_PROJECT_ID: Optional[str] = None
    YOUTUBE_API_KEY: str
    YES_API_KEY: str

    @property
    def get_redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding='utf-8'
    )


settings = Settings()
