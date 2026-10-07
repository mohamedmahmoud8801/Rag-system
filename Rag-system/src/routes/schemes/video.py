from typing import Optional
from pydantic import BaseModel, Field


class VideoIngestRequest(BaseModel):
    video_url: str = Field(..., min_length=1)
    provider: str = "youtube"
    language: Optional[str] = None
    chunk_size: int = Field(default=1200, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)


class VideoIngestResponse(BaseModel):
    success: bool
    video_id: str
    video_url: str
    provider: str
    source_type: str
    language: Optional[str]
    duration: Optional[float]
    transcript_segments: int
    asset_id: int
    asset_name: str
    chunks_created: int
    chunk_ids: list[int]
    collection_name: str