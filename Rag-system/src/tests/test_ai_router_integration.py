import pytest

from main import app, startup_span, shutdown_span
from controllers.AIRouterController import AIRouterController
from models.ProjectModel import ProjectModel

@pytest.mark.asyncio
async def test_real_router_sql_e2e():

    await startup_span()
    project_model = await ProjectModel.create_instance(
    db_client=app.db_client
)

    project = await project_model.get_project_or_create_one(
        project_id=1
    )

    try:
        controller = AIRouterController(
            generation_client=app.generation_client,
            sql_template_parser=app.sql_template_parser,
            template_parser=app.template_parser,
            vectordb_client=app.vectordb_client,
            embedding_client=app.embedding_client,
            reranker_client=app.reranker_client,
        )

        result = await controller.route(
            query="How many customers are from Egypt?",
            project=project,
            project_id=1,
            database_url="sqlite:///assets/database/sql/ecommerce.db",
            provider="sqlite",
            max_rows=10,
            max_retries=2,
        )

        print("\n========== REAL ROUTER RESULT ==========")
        print(result)

        assert result["intent"] == "sql"

        assert "result" in result

        sql_result = result["result"]

        assert "sql" in sql_result
        assert "result" in sql_result

        rows = sql_result["result"]["rows"]

        assert len(rows) == 1

        # COUNT(*) should return 2 Egyptian customers
        assert rows == [{"COUNT(*)": 2}]
    finally:
        await shutdown_span()


@pytest.mark.asyncio
async def test_real_router_rag_e2e():
    await startup_span()

    try:
        project_model = await ProjectModel.create_instance(
            db_client=app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=1
        )

        controller = AIRouterController(
            generation_client=app.generation_client,
            sql_template_parser=app.sql_template_parser,
            template_parser=app.template_parser,
            vectordb_client=app.vectordb_client,
            embedding_client=app.embedding_client,
            reranker_client=app.reranker_client,
        )

        result = await controller.route(
            query=(
                "Search the uploaded documents and answer: "
                "why is the dot product scaled by 1/sqrt(d_k)?"
            ),
            project=project,
            project_id=1,
            limit=5,
            top_k=5,
        )

        print("\n========== REAL ROUTER RAG RESULT ==========")
        print(result)

        assert result["intent"] == "rag"
        assert result["answer"]
        assert isinstance(result["answer"], str)
        assert len(result["answer"].strip()) > 0

    finally:
        await shutdown_span()



@pytest.mark.asyncio
async def test_real_router_knowledge_qa_e2e():
    await startup_span()

    try:
        project_model = await ProjectModel.create_instance(
            db_client=app.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=1
        )

        controller = AIRouterController(
            generation_client=app.generation_client,
            sql_template_parser=app.sql_template_parser,
            template_parser=app.template_parser,
            vectordb_client=app.vectordb_client,
            embedding_client=app.embedding_client,
            reranker_client=app.reranker_client,
        )

        result = await controller.route(
            query=(
                "Using the uploaded documents, explain "
                "why the dot product is scaled by 1/sqrt(d_k)."
            ),
            project=project,
            project_id=1,
            limit=5,
            top_k=5,
        )

        print("\n========== REAL ROUTER KNOWLEDGE RESULT ==========")
        print(result)

        assert result["intent"] == "knowledge_qa"
        assert result["result"] is not None

    finally:
        await shutdown_span()