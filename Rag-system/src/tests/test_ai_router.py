import pytest

from stores.router.AIRouter import AIRouter
from stores.router.RouterEnums import RouterIntentEnum
from controllers.AIRouterController import AIRouterController


# ============================================================
# Fake generation client
# ============================================================

class FakeGenerationClient:

    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_text(
        self,
        prompt,
        max_output_tokens=None,
        temperature=None,
        **kwargs
    ):
        self.calls.append({
            "prompt": prompt,
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
        })

        return self.response


# ============================================================
# Router classification tests
# ============================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent",
    [
        RouterIntentEnum.RAG.value,
        RouterIntentEnum.SQL.value,
        RouterIntentEnum.KNOWLEDGE_QA.value,
        RouterIntentEnum.KNOWLEDGE_SUMMARY.value,
        RouterIntentEnum.KNOWLEDGE_KEY_POINTS.value,
        RouterIntentEnum.KNOWLEDGE_NOTES.value,
        RouterIntentEnum.KNOWLEDGE_FLASHCARDS.value,
        RouterIntentEnum.KNOWLEDGE_QUIZ.value,
    ],
)
async def test_router_classify_valid_intents(intent):

    generation_client = FakeGenerationClient(
        response={"intent": intent}
    )

    router = AIRouter(
        generation_client=generation_client
    )

    result = await router.classify(
        query="test query"
    )

    assert result == intent

    assert len(generation_client.calls) == 1

    call = generation_client.calls[0]

    assert call["max_output_tokens"] == 100
    assert call["temperature"] == 0.0


@pytest.mark.asyncio
async def test_router_rejects_empty_query():

    generation_client = FakeGenerationClient(
        response={"intent": "rag"}
    )

    router = AIRouter(
        generation_client=generation_client
    )

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await router.classify("")


@pytest.mark.asyncio
async def test_router_rejects_empty_llm_response():

    generation_client = FakeGenerationClient(
        response=""
    )

    router = AIRouter(
        generation_client=generation_client
    )

    with pytest.raises(
        ValueError,
        match="Router returned an empty response"
    ):
        await router.classify("test query")


@pytest.mark.asyncio
async def test_router_rejects_invalid_intent():

    generation_client = FakeGenerationClient(
        response={"intent": "invalid_intent"}
    )

    router = AIRouter(
        generation_client=generation_client
    )

    with pytest.raises(
        ValueError,
        match="Invalid router intent"
    ):
        await router.classify("test query")


@pytest.mark.asyncio
async def test_router_parses_json_code_block():

    generation_client = FakeGenerationClient(
        response='```json\n{"intent": "sql"}\n```'
    )

    router = AIRouter(
        generation_client=generation_client
    )

    result = await router.classify(
        query="How many customers are there?"
    )

    assert result == RouterIntentEnum.SQL.value


@pytest.mark.asyncio
async def test_router_rejects_invalid_json():

    generation_client = FakeGenerationClient(
        response='this is not json'
    )

    router = AIRouter(
        generation_client=generation_client
    )

    with pytest.raises(
        ValueError,
        match="Invalid router JSON response"
    ):
        await router.classify("test query")


# ============================================================
# Controller routing tests
# ============================================================

class FakeSQLController:

    def __init__(self):
        self.calls = []

    async def query(
        self,
        provider,
        database_url,
        question,
        max_rows,
        max_retries,
    ):
        self.calls.append({
            "provider": provider,
            "database_url": database_url,
            "question": question,
            "max_rows": max_rows,
            "max_retries": max_retries,
        })

        return {
            "sql": "SELECT 1",
            "result": {"value": 1},
        }


class FakeKnowledgeController:

    def __init__(self):
        self.calls = []

    async def answer(self, **kwargs):
        return await self._handle("answer", **kwargs)

    async def summarize(self, **kwargs):
        return await self._handle("summarize", **kwargs)

    async def extract_key_points(self, **kwargs):
        return await self._handle("extract_key_points", **kwargs)

    async def create_notes(self, **kwargs):
        return await self._handle("create_notes", **kwargs)

    async def generate_flashcards(self, **kwargs):
        return await self._handle("generate_flashcards", **kwargs)

    async def generate_quiz(self, **kwargs):
        return await self._handle("generate_quiz", **kwargs)

    async def _handle(self, method, **kwargs):
        self.calls.append({
            "method": method,
            "kwargs": kwargs,
        })

        return {
            "handled_by": method,
        }


class FakeNLPController:

    def __init__(self):
        self.calls = []

    async def answer_rag_question(
        self,
        project,
        query,
        limit,
    ):
        self.calls.append({
            "project": project,
            "query": query,
            "limit": limit,
        })

        return (
            "RAG answer",
            "full prompt",
            [],
        )


def build_controller(intent):

    generation_client = FakeGenerationClient(
        response={"intent": intent}
    )

    controller = object.__new__(AIRouterController)

    controller.router = AIRouter(
        generation_client=generation_client
    )

    controller.sql_controller = FakeSQLController()
    controller.knowledge_controller = FakeKnowledgeController()
    controller.nlp_controller = FakeNLPController()

    return controller


# ============================================================
# SQL routing
# ============================================================

@pytest.mark.asyncio
async def test_controller_routes_sql():

    controller = build_controller(
        RouterIntentEnum.SQL.value
    )

    result = await controller.route(
        query="How many customers are from Egypt?",
        database_url="sqlite:///test.db",
        provider="sqlite",
        max_rows=10,
        max_retries=2,
    )

    assert result["intent"] == RouterIntentEnum.SQL.value

    assert result["result"]["sql"] == "SELECT 1"

    assert len(controller.sql_controller.calls) == 1

    call = controller.sql_controller.calls[0]

    assert call["database_url"] == "sqlite:///test.db"
    assert call["provider"] == "sqlite"
    assert call["question"] == "How many customers are from Egypt?"
    assert call["max_rows"] == 10
    assert call["max_retries"] == 2


@pytest.mark.asyncio
async def test_controller_sql_requires_database_url():

    controller = build_controller(
        RouterIntentEnum.SQL.value
    )

    with pytest.raises(
        ValueError,
        match="database_url is required"
    ):
        await controller.route(
            query="How many customers are from Egypt?"
        )


# ============================================================
# Knowledge routing
# ============================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent,expected_method",
    [
        (
            RouterIntentEnum.KNOWLEDGE_QA.value,
            "answer",
        ),
        (
            RouterIntentEnum.KNOWLEDGE_SUMMARY.value,
            "summarize",
        ),
        (
            RouterIntentEnum.KNOWLEDGE_KEY_POINTS.value,
            "extract_key_points",
        ),
        (
            RouterIntentEnum.KNOWLEDGE_NOTES.value,
            "create_notes",
        ),
        (
            RouterIntentEnum.KNOWLEDGE_FLASHCARDS.value,
            "generate_flashcards",
        ),
        (
            RouterIntentEnum.KNOWLEDGE_QUIZ.value,
            "generate_quiz",
        ),
    ],
)
async def test_controller_routes_knowledge(
    intent,
    expected_method,
):

    controller = build_controller(intent)

    project = object()

    result = await controller.route(
        query="Tell me about attention.",
        project=project,
        limit=10,
        top_k=5,
        max_output_tokens=200,
        temperature=0.0,
    )

    assert result["intent"] == intent

    assert result["result"]["handled_by"] == expected_method

    assert len(controller.knowledge_controller.calls) == 1

    call = controller.knowledge_controller.calls[0]

    assert call["method"] == expected_method

    assert call["kwargs"]["project"] is project
    assert call["kwargs"]["query"] == "Tell me about attention."
    assert call["kwargs"]["limit"] == 10
    assert call["kwargs"]["top_k"] == 5
    assert call["kwargs"]["max_output_tokens"] == 200
    assert call["kwargs"]["temperature"] == 0.0


@pytest.mark.asyncio
async def test_controller_knowledge_requires_project():

    controller = build_controller(
        RouterIntentEnum.KNOWLEDGE_QA.value
    )

    with pytest.raises(
        ValueError,
        match="Project is required"
    ):
        await controller.route(
            query="What is attention?"
        )


# ============================================================
# RAG routing
# ============================================================

@pytest.mark.asyncio
async def test_controller_routes_rag():

    controller = build_controller(
        RouterIntentEnum.RAG.value
    )

    project = object()

    result = await controller.route(
        query="What is self-attention?",
        project=project,
        limit=7,
    )

    assert result["intent"] == RouterIntentEnum.RAG.value
    assert result["answer"] == "RAG answer"
    assert result["full_prompt"] == "full prompt"
    assert result["chat_history"] == []

    assert len(controller.nlp_controller.calls) == 1

    call = controller.nlp_controller.calls[0]

    assert call["project"] is project
    assert call["query"] == "What is self-attention?"
    assert call["limit"] == 7


@pytest.mark.asyncio
async def test_controller_rag_requires_project():

    controller = build_controller(
        RouterIntentEnum.RAG.value
    )

    with pytest.raises(
        ValueError,
        match="Project is required for RAG"
    ):
        await controller.route(
            query="What is self-attention?"
        )


# ============================================================
# Unsupported intent
# ============================================================

@pytest.mark.asyncio
async def test_controller_rejects_unsupported_intent():

    controller = build_controller(
        "unsupported"
    )

    # Bypass AIRouter validation so we can specifically test
    # the controller's final fallback branch.
    controller.router.classify = lambda **kwargs: None

    async def fake_classify(**kwargs):
        return "unsupported"

    controller.router.classify = fake_classify

    with pytest.raises(
        ValueError,
        match="Unsupported router intent"
    ):
        await controller.route(
            query="test"
        )
