from fastapi import APIRouter, HTTPException, Request
from controllers.KnowledgeController import KnowledgeController
from models.ProjectModel import ProjectModel
from routes.schemes.knowledge import KnowledgeRequest
import traceback

knowledge_router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge"])

def get_knowledge_controller(request: Request):
    return KnowledgeController(
        db_client=request.app.db_client,
        vectordb_client=request.app.vectordb_client,
        embedding_client=request.app.embedding_client,
        reranker_client=request.app.reranker_client,
        generation_client=request.app.generation_client,
        template_parser=request.app.template_parser,
    )

async def get_project(request: Request, project_id: int):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)
    if not project: raise HTTPException(status_code=400, detail="Project not found.")
    return project

def serialize_documents(documents):
    serialized = []
    for d in documents or []:
        if hasattr(d, "model_dump"): serialized.append(d.model_dump())
        elif hasattr(d, "dict"): serialized.append(d.dict())
        elif isinstance(d, dict): serialized.append(d)
        else: serialized.append({"content": getattr(d, "page_content", str(d))})
    return serialized

@knowledge_router.post("/qa/{project_id}")
async def knowledge_qa(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.answer(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "qa", "query": result.get("query", ""), "answer": result.get("answer"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/summary/{project_id}")
async def knowledge_summary(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.summarize(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "summary", "query": result.get("query", ""), "summary": result.get("summary"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/faq/{project_id}")
async def knowledge_faq(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.generate_faq(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "faq", "query": result.get("query", ""), "faq": result.get("faq"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/mindmap/{project_id}")
async def knowledge_mindmap(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.generate_mindmap(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "mindmap", "query": result.get("query", ""), "mindmap": result.get("mindmap"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/key-points/{project_id}")
async def knowledge_key_points(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.extract_key_points(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "key_points", "query": result.get("query", ""), "key_points": result.get("key_points"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/notes/{project_id}")
async def knowledge_notes(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.create_notes(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "notes", "query": result.get("query", ""), "notes": result.get("notes"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/flashcards/{project_id}")
async def knowledge_flashcards(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.generate_flashcards(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "flashcards", "query": result.get("query", ""), "flashcards": result.get("flashcards"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@knowledge_router.post("/quiz/{project_id}")
async def knowledge_quiz(request: Request, project_id: int, knowledge_request: KnowledgeRequest):
    try:
        project = await get_project(request, project_id)
        controller = get_knowledge_controller(request)
        result = await controller.generate_quiz(
            db_client=request.app.db_client, project=project, query=knowledge_request.query or "", 
            file_id=knowledge_request.file_id, max_output_tokens=knowledge_request.max_output_tokens, temperature=knowledge_request.temperature
        )
        return {"success": True, "task": "quiz", "query": result.get("query", ""), "quiz": result.get("quiz"), "documents": serialize_documents(result.get("documents", []))}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))