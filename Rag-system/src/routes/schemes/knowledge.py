from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeRequest(BaseModel):

    query: str = Field(
        ...,
        min_length=1
    )

    limit: int = Field(
        default=10,
        ge=1,
        le=50
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20
    )

    max_output_tokens: Optional[int] = Field(
        default=None,
        ge=1
    )

    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0
    )
