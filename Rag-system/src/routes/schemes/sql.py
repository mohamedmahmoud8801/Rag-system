from typing import List, Optional

from pydantic import BaseModel, Field
from stores.sql.SQLEnums import SQLProviderEnum


class SQLSchemaRequest(BaseModel):

    database_url: str

    provider: str = "sqlite"

    tables: Optional[List[str]] = None


class SQLExecuteRequest(BaseModel):

    database_url: str

    provider: str = "sqlite"

    query: str = Field(
        ...,
        min_length=1
    )

    max_rows: int = Field(
        default=100,
        ge=1,
        le=1000
    )


class SQLQueryRequest(BaseModel):

    database_url: str

    provider: str = "sqlite"

    question: str = Field(
        ...,
        min_length=1
    )

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

class ExcelSQLIngestRequest(BaseModel):

    project_id: str

    file_id: str

    provider: SQLProviderEnum

    database_url: str