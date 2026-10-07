from fastapi import APIRouter, HTTPException, Request

from controllers.KnowledgeController import KnowledgeController
from models.ProjectModel import ProjectModel

from routes.schemes.knowledge import KnowledgeRequest


knowledge_router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["Knowledge"],
)


def get_knowledge_controller(request: Request):

    return KnowledgeController(
        vectordb_client=request.app.vectordb_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser,
    )


async def get_project(
    request: Request,
    project_id: int,
):

    project_model = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project = await project_model.get_project_or_create_one(
        project_id=project_id
    )

    if not project:
        raise HTTPException(
            status_code=400,
            detail="Project not found."
        )

    return project


def serialize_documents(documents):

    serialized_documents = []

    for document in documents or []:

        if hasattr(document, "dict"):
            serialized_documents.append(
                document.dict()
            )

        elif hasattr(document, "model_dump"):
            serialized_documents.append(
                document.model_dump()
            )

        elif isinstance(document, dict):
            serialized_documents.append(
                document
            )

        else:
            serialized_documents.append(
                {
                    "content": getattr(
                        document,
                        "page_content",
                        str(document)
                    )
                }
            )

    return serialized_documents


# ============================================================
# Question Answering
# ============================================================

@knowledge_router.post("/qa/{project_id}")
async def knowledge_qa(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.answer(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "qa",
            "query": result["query"],
            "answer": result["answer"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Summary
# ============================================================

@knowledge_router.post("/summary/{project_id}")
async def knowledge_summary(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.summarize(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "summary",
            "query": result["query"],
            "summary": result["summary"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Key Points
# ============================================================

@knowledge_router.post("/key-points/{project_id}")
async def knowledge_key_points(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.extract_key_points(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "key_points",
            "query": result["query"],
            "key_points": result["key_points"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Notes
# ============================================================

@knowledge_router.post("/notes/{project_id}")
async def knowledge_notes(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.create_notes(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "notes",
            "query": result["query"],
            "notes": result["notes"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Flashcards
# ============================================================

@knowledge_router.post("/flashcards/{project_id}")
async def knowledge_flashcards(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.generate_flashcards(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "flashcards",
            "query": result["query"],
            "flashcards": result["flashcards"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# Quiz
# ============================================================

@knowledge_router.post("/quiz/{project_id}")
async def knowledge_quiz(
    request: Request,
    project_id: int,
    knowledge_request: KnowledgeRequest,
):

    try:

        project = await get_project(
            request=request,
            project_id=project_id,
        )

        controller = get_knowledge_controller(request)

        result = await controller.generate_quiz(
            project=project,
            query=knowledge_request.query,
            limit=knowledge_request.limit,
            top_k=knowledge_request.top_k,
            max_output_tokens=knowledge_request.max_output_tokens,
            temperature=knowledge_request.temperature,
        )

        return {
            "success": True,
            "task": "quiz",
            "query": result["query"],
            "quiz": result["quiz"],
            "documents": serialize_documents(
                result.get("documents", [])
            ),
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
