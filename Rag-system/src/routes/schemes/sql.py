from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field
from stores.sql.SQLEnums import SQLProviderEnum


# database_url / provider are OPTIONAL everywhere: when omitted the
# server uses SQL_DATABASE_URL / SQL_PROVIDER from its settings. A custom
# database_url is only accepted when SQL_ALLOW_CLIENT_DATABASE_URL=true.

class SQLSchemaRequest(BaseModel):

    database_url: Optional[str] = None

    provider: Optional[str] = None

    tables: Optional[List[str]] = None


class SQLExecuteRequest(BaseModel):

    database_url: Optional[str] = None

    provider: Optional[str] = None

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

    database_url: Optional[str] = None

    provider: Optional[str] = None

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

    project_id: Union[int, str]

    file_id: str

    # Not accepted any more: Excel sheets are stored in the project's own
    # Excel database. Left here only to give old clients a clear error.
    provider: Optional[SQLProviderEnum] = None

    database_url: Optional[str] = None

    # "fail": stop if a table with the same name already exists
    # "replace": drop and recreate tables with the same name
    if_exists: Literal["fail", "replace"] = "fail"