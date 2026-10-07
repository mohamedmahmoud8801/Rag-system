from fastapi import APIRouter, Request, HTTPException

from routes.schemes.video import (
    VideoIngestRequest,
    VideoIngestResponse,
)

from controllers.VideoController import VideoController


video_router = APIRouter(
    prefix="/api/v1/video",
    tags=["Video"],
)


@video_router.post(
    "/ingest/{project_id}",
    response_model=VideoIngestResponse
)
async def ingest_video(
    request: Request,
    project_id: int,
    body: VideoIngestRequest
):
    try:
        controller = VideoController(
            db_client=request.app.db_client,
            vectordb_client=request.app.vectordb_client,
            embedding_client=request.app.embedding_client,
            generation_client=request.app.generation_client,
            reranker_client=request.app.reranker_client,
            template_parser=request.app.template_parser,
        )

        result = await controller.ingest_video(
            project_id=project_id,
            video_url=body.video_url,
            provider=body.provider,
            language=body.language,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )