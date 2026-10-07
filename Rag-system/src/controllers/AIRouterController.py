from stores.router.AIRouter import AIRouter
from stores.router.RouterEnums import RouterIntentEnum

from controllers.KnowledgeController import KnowledgeController
from controllers.NLPController import NLPController
from controllers.SQLController import SQLController


class AIRouterController:

    def __init__(
        self,
        generation_client,
        sql_template_parser,
        template_parser,
        vectordb_client,
        embedding_client,
        reranker_client,
    ):
        self.router = AIRouter(
            generation_client=generation_client
        )

        self.sql_controller = SQLController(
            generation_client=generation_client,
            sql_template_parser=sql_template_parser,
        )

        self.knowledge_controller = KnowledgeController(
            vectordb_client=vectordb_client,
            embedding_client=embedding_client,
            reranker_client=reranker_client,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            reranker_client=reranker_client,
            template_parser=template_parser,
        )

    async def route(
        self,
        query: str,
        project=None,
        project_id: int = 1,
        limit: int = 10,
        top_k: int = 5,
        max_output_tokens: int = None,
        temperature: float = None,
        database_url: str = None,
        provider: str = "sqlite",
        max_rows: int = 100,
        max_retries: int = 2,
    ):

        intent = await self.router.classify(
            query=query,
            max_output_tokens=100,
            temperature=0.0,
        )

        # ---------------------------------------------------------
        # SQL
        # ---------------------------------------------------------

        if intent == RouterIntentEnum.SQL.value:

            if not database_url:
                raise ValueError(
                    "database_url is required when router intent is SQL."
                )

            result = await self.sql_controller.query(
                provider=provider,
                database_url=database_url,
                question=query,
                max_rows=max_rows,
                max_retries=max_retries,
            )

            return {
                "intent": intent,
                "result": result,
            }

        # ---------------------------------------------------------
        # Knowledge
        # ---------------------------------------------------------

        knowledge_methods = {
            RouterIntentEnum.KNOWLEDGE_QA.value:
                self.knowledge_controller.answer,

            RouterIntentEnum.KNOWLEDGE_SUMMARY.value:
                self.knowledge_controller.summarize,

            RouterIntentEnum.KNOWLEDGE_KEY_POINTS.value:
                self.knowledge_controller.extract_key_points,

            RouterIntentEnum.KNOWLEDGE_NOTES.value:
                self.knowledge_controller.create_notes,

            RouterIntentEnum.KNOWLEDGE_FLASHCARDS.value:
                self.knowledge_controller.generate_flashcards,

            RouterIntentEnum.KNOWLEDGE_QUIZ.value:
                self.knowledge_controller.generate_quiz,
        }

        if intent in knowledge_methods:

            if project is None:
                raise ValueError(
                    "Project is required for Knowledge requests."
                )

            method = knowledge_methods[intent]

            result = await method(
                project=project,
                query=query,
                limit=limit,
                top_k=top_k,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            )

            return {
                "intent": intent,
                "result": result,
            }

        # ---------------------------------------------------------
        # RAG
        # ---------------------------------------------------------

        if intent == RouterIntentEnum.RAG.value:

            if project is None:
                raise ValueError(
                    "Project is required for RAG."
                )

            answer, full_prompt, chat_history = (
                await self.nlp_controller.answer_rag_question(
                    project=project,
                    query=query,
                    limit=limit,
                )
            )

            return {
                "intent": intent,
                "answer": answer,
                "full_prompt": full_prompt,
                "chat_history": chat_history,
            }

        raise ValueError(
            f"Unsupported router intent: {intent}"
        )
