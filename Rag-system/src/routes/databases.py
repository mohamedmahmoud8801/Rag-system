from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from controllers.DatabaseConnectionController import (
    ConnectionTestFailed,
    DatabaseConnectionController,
)
from routes.schemes.databases import ConnectionCreateRequest, ConnectionParams
from stores.sql.ConnectionSecurity import ConnectionNotAllowed


databases_router = APIRouter(
    prefix="/api/v1/databases",
    tags=["Databases"],
)

_BAD_REQUEST = (ConnectionNotAllowed, ConnectionTestFailed)


# "/test" is declared before "/{project_id}" so it is matched first.

@databases_router.post("/test")
async def test_connection(body: ConnectionParams):
    """Try a connection without saving it. Always 200: see `ok` / `error`."""

    return await DatabaseConnectionController().test(body.to_params())


@databases_router.post("/{project_id}", status_code=201)
async def create_connection(project_id: int, body: ConnectionCreateRequest):
    """Test, then save (encrypted). Use `database_url` ("conn://...") in the SQL endpoints."""

    try:
        connection = await DatabaseConnectionController().create(
            project_id=project_id,
            name=body.name,
            params=body.to_params(),
        )
    except _BAD_REQUEST as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"success": True, "connection": connection}


@databases_router.post("/{project_id}/sqlite-upload", status_code=201)
async def upload_sqlite(
    project_id: int,
    name: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a SQLite file from the browser and connect it (read-only)."""

    try:
        connection = await DatabaseConnectionController().create_from_sqlite_upload(
            project_id=project_id,
            name=name,
            upload=file,
        )
    except _BAD_REQUEST as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"success": True, "connection": connection}


@databases_router.get("/{project_id}")
async def list_connections(project_id: int):

    return {
        "success": True,
        "connections": DatabaseConnectionController().list(project_id),
    }


@databases_router.delete("/{project_id}/{connection_id}")
async def delete_connection(project_id: int, connection_id: str):

    if not DatabaseConnectionController().delete(project_id, connection_id):
        raise HTTPException(status_code=404, detail="Connection not found.")

    return {"success": True}