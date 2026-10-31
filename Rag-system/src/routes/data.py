from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
import asyncio
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController, NLPController
import aiofiles
from models import ResponseSignal
import logging
from .schemes.data import ProcessRequest
from models.ProjectModel import ProjectModel
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.db_schemes import DataChunk, Asset
from models.enums.AssetTypeEnum import AssetTypeEnum
from pydantic import BaseModel
from sqlalchemy import delete, text

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

class DeleteFilesRequest(BaseModel):
    file_ids: list[str]

@data_router.post("/upload/{project_id}")
async def upload_data(
    request: Request,
    project_id: int,
    file: UploadFile,
    app_settings: Settings = Depends(get_settings),
):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    data_controller = DataController()
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": result_signal})

    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path, file_id = data_controller.generate_unique_filepath(orig_file_name=file.filename, project_id=project_id)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error while uploading file: {e}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignal.FILE_UPLOAD_FAILED.value})

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_resource = Asset(
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_id,
        asset_size=os.path.getsize(file_path),
        asset_config={"original_filename": file.filename}
    )
    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(content={"signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value, "file_id": str(asset_record.asset_id), "asset_name": file_id})


@data_router.post("/process/{project_id}")
async def process_endpoint(
    request: Request,
    project_id: int,
    process_request: ProcessRequest
):
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
        template_parser=request.app.template_parser,
    )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)

    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(asset_project_id=project.project_id, asset_name=process_request.file_id)
        if asset_record is None:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignal.FILE_ID_ERROR.value})
        project_files = [asset_record]
    else:
        project_files = await asset_model.get_all_project_assets(asset_project_id=project.project_id, asset_type=AssetTypeEnum.FILE.value)

    if len(project_files) == 0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignal.NO_FILES_ERROR.value})

    process_controller = ProcessController(project_id=project_id)
    no_records = 0
    no_files = 0
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)

    if do_reset == 1:
        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
        _ = await request.app.vectordb_client.delete_collection(collection_name=collection_name)
        _ = await chunk_model.delete_chunks_by_project_id(project_id=project.project_id)

    for asset in project_files:
        asset_id = asset.asset_id
        file_id = asset.asset_name
        original_filename = (asset.asset_config or {}).get("original_filename") or file_id

        file_content = process_controller.get_file_content(file_id=file_id)
        if file_content is None:
            logger.error(f"Error while processing file: {file_id}")
            continue

        for document in file_content:
            if document.metadata is None:
                document.metadata = {}
            document.metadata["original_filename"] = original_filename

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size
        )

        if file_chunks is None or len(file_chunks) == 0:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseSignal.PROCESSING_FAILED.value})

        file_chunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.project_id,
                chunk_asset_id=asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1

    return JSONResponse(content={"signal": ResponseSignal.PROCESSING_SUCCESS.value, "inserted_chunks": no_records, "processed_files": no_files})


# =========================================================
# DELETION ENDPOINTS (Fixing Foreign Key Issue)
# =========================================================

@data_router.delete("/reset/{project_id}")
async def reset_project_data(request: Request, project_id: int):
    deleted = {"chunks": 0, "assets": 0, "files": 0, "collection": False, "excel_db": False}
    errors = []

    try:
        nlp_controller = NLPController(
            vectordb_client=request.app.vectordb_client,
            generation_client=request.app.generation_client,
            embedding_client=request.app.embedding_client,
            reranker_client=request.app.reranker_client,
            template_parser=request.app.template_parser,
        )
        collection_name = nlp_controller.create_collection_name(project_id=project_id)
        
        # Drop the vector table with CASCADE to remove foreign key constraints
        async with request.app.db_client() as session:
            await session.execute(text(f"DROP TABLE IF EXISTS {collection_name} CASCADE;"))
            await session.execute(delete(DataChunk).where(DataChunk.chunk_project_id == project_id))
            await session.execute(delete(Asset).where(Asset.asset_project_id == project_id))
            await session.commit()
        deleted["collection"] = True
    except Exception as e:
        logger.error(f"[RESET] DB/Collection deletion failed: {e}")
        errors.append(f"db: {e}")

    project_path = ProjectController().get_project_path(project_id=project_id)
    try:
        if os.path.isdir(project_path):
            for name in os.listdir(project_path):
                fp = os.path.join(project_path, name)
                if os.path.isfile(fp):
                    os.remove(fp)
                    deleted["files"] += 1
    except Exception as e:
        errors.append(f"files: {e}")

    try:
        excel_db = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "database", "excel", f"project_{project_id}.db")
        if os.path.isfile(excel_db):
            os.remove(excel_db)
            deleted["excel_db"] = True
    except Exception as e:
        errors.append(f"excel_db: {e}")

    return JSONResponse(content={"success": len(errors) == 0, "deleted": deleted, "errors": errors})


@data_router.post("/delete-files/{project_id}")
async def delete_selected_files(request: Request, project_id: int, body: DeleteFilesRequest):
    """Delete specific files by their asset_name (file_id)"""
    errors = []
    deleted_count = 0

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
        template_parser=request.app.template_parser,
    )
    collection_name = nlp_controller.create_collection_name(project_id=project_id)
    project_path = ProjectController().get_project_path(project_id=project_id)

    for file_id in body.file_ids:
        try:
            async with request.app.db_client() as session:
                # Get Asset
                asset_stmt = text(f"SELECT asset_id FROM assets WHERE asset_name = :file_id AND asset_project_id = :pid")
                result = await session.execute(asset_stmt, {"file_id": file_id, "pid": project_id})
                asset_row = result.fetchone()
                
                if not asset_row:
                    continue
                
                asset_id = asset_row[0]

                # Get Chunks & Delete from Vector Table
                chunk_stmt = text(f"SELECT chunk_id FROM chunks WHERE chunk_asset_id = :aid")
                chunk_result = await session.execute(chunk_stmt, {"aid": asset_id})
                chunk_ids = [row[0] for row in chunk_result.fetchall()]

                if chunk_ids:
                    ids_str = ",".join(str(cid) for cid in chunk_ids)
                    await session.execute(text(f"DELETE FROM {collection_name} WHERE chunk_id IN ({ids_str})"))
                    await session.execute(text(f"DELETE FROM chunks WHERE chunk_id IN ({ids_str})"))

                # Delete Asset
                await session.execute(text(f"DELETE FROM assets WHERE asset_id = {asset_id}"))
                await session.commit()

            # Delete from Disk
            file_path = os.path.join(project_path, file_id)
            if os.path.isfile(file_path):
                os.remove(file_path)

            deleted_count += 1
        except Exception as e:
            logger.error(f"[DELETE FILE] Error deleting {file_id}: {e}")
            errors.append(f"{file_id}: {e}")

    return JSONResponse(content={"success": len(errors) == 0, "deleted_count": deleted_count, "errors": errors})