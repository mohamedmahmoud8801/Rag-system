from fastapi import APIRouter, HTTPException, Request

from controllers.AIRouterController import AIRouterController
from models.ProjectModel import ProjectModel
from routes.schemes.router import RouterQueryRequest


router_router = APIRouter(
    prefix="/api/v1/router",
    tags=["AI Router"],
)


def get_router_controller(request: Request):

    return AIRouterController(
        generation_client=request.app.generation_client,
        sql_template_parser=request.app.sql_template_parser,
        template_parser=request.app.template_parser,
        vectordb_client=request.app.vectordb_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
    )


@router_router.post("/query")
async def route_query(
    request: Request,
    router_request: RouterQueryRequest,
):

    try:

        project_model = await ProjectModel.create_instance(
            db_client=request.app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=router_request.project_id
        )

        if not project:
            raise HTTPException(
                status_code=400,
                detail="Project not found."
            )

        controller = get_router_controller(request)

        result = await controller.route(
            query=router_request.query,
            project=project,
            project_id=router_request.project_id,
            limit=router_request.limit,
            top_k=router_request.top_k,
            max_output_tokens=router_request.max_output_tokens,
            temperature=router_request.temperature,
            database_url=router_request.database_url,
            provider=router_request.provider,
            max_rows=router_request.max_rows,
            max_retries=router_request.max_retries,
        )

        return {
            "success": True,
            "query": router_request.query,
            **result,
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
