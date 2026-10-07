from fastapi import APIRouter, HTTPException, Request

from controllers.SQLController import SQLController
from controllers.ExcelSQLController import ExcelSQLController
from routes.schemes.sql import ExcelSQLIngestRequest

from routes.schemes.sql import (
    SQLSchemaRequest,
    SQLExecuteRequest,
    SQLQueryRequest,
)


sql_router = APIRouter(
    prefix="/sql",
    tags=["SQL"],
)


def get_sql_controller(request: Request):

    return SQLController(
        generation_client=request.app.generation_client,
        sql_template_parser=request.app.sql_template_parser,
    )


# ============================================================
# Schema
# ============================================================

@sql_router.post("/schema")
async def get_schema(
    request: Request,
    sql_request: SQLSchemaRequest,
):

    try:

        controller = get_sql_controller(request)

        schema = await controller.get_schema(
            provider=sql_request.provider,
            database_url=sql_request.database_url,
            tables=sql_request.tables,
        )

        return {
            "success": True,
            "schema": schema,
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Tables
# ============================================================

@sql_router.post("/tables")
async def get_tables(
    request: Request,
    sql_request: SQLSchemaRequest,
):

    try:

        controller = get_sql_controller(request)

        tables = await controller.get_tables(
            provider=sql_request.provider,
            database_url=sql_request.database_url,
        )

        return {
            "success": True,
            "tables": tables,
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Execute SQL
# ============================================================

@sql_router.post("/execute")
async def execute(
    request: Request,
    sql_request: SQLExecuteRequest,
):

    try:

        controller = get_sql_controller(request)

        result = await controller.execute(
            provider=sql_request.provider,
            database_url=sql_request.database_url,
            query=sql_request.query,
            max_rows=sql_request.max_rows,
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Generate SQL
# ============================================================

@sql_router.post("/generate")
async def generate_sql(
    request: Request,
    sql_request: SQLQueryRequest,
):

    try:

        controller = get_sql_controller(request)

        result = await controller.generate_sql(
            provider=sql_request.provider,
            database_url=sql_request.database_url,
            question=sql_request.question,
            max_rows=sql_request.max_rows,
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Natural Language → SQL → Validate → Execute
# ============================================================

@sql_router.post("/query")
async def query_sql(
    request: Request,
    sql_request: SQLQueryRequest,
):

    try:

        controller = get_sql_controller(request)

        result = await controller.query(
            provider=sql_request.provider,
            database_url=sql_request.database_url,
            question=sql_request.question,
            max_rows=sql_request.max_rows,
            max_retries=sql_request.max_retries,
        )

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
@sql_router.post("/ingest")
async def ingest_excel(
    request: ExcelSQLIngestRequest
):

    try:

        controller = ExcelSQLController(
            project_id=request.project_id,
            provider=request.provider.value,
            database_url=request.database_url
        )

        result = await controller.ingest(
            file_id=request.file_id
        )

        return {
            "success": True,
            "result": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )