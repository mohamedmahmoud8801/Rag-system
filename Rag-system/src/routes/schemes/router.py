from typing import Optional

from pydantic import BaseModel, Field


class RouterQueryRequest(BaseModel):

    query: str = Field(..., min_length=1)

    # Used by RAG / Knowledge
    project_id: int = Field(default=1, ge=1)

    # Retrieval settings
    limit: int = Field(default=10, ge=1, le=50)
    top_k: int = Field(default=5, ge=1, le=20)

    # Generation settings
    max_output_tokens: Optional[int] = Field(
        default=None,
        ge=1
    )

    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0
    )

    # Used only when intent = SQL
    database_url: Optional[str] = None
    provider: str = "sqlite"

    max_rows: int = Field(
        default=100,
        ge=1,
        le=1000
    )

    max_retries: int = Field(
        default=2,
        ge=0,
        le=5
    )
