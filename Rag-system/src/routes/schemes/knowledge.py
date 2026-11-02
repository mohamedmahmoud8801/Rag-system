from typing import Optional
from pydantic import BaseModel, Field

class KnowledgeRequest(BaseModel):
    query: Optional[str] = None
    file_id: Optional[str] = None
    max_output_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)