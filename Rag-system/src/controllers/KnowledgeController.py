from services.knowledge import (
    KnowledgeRetrievalService,
    KnowledgeQAService,
    KnowledgeSummaryService,
    KnowledgeKeyPointsService,
    KnowledgeNotesService,
    KnowledgeFlashcardsService,
    KnowledgeQuizService,
)


class KnowledgeController:

    def __init__(
        self,
        vectordb_client,
        embedding_client,
        reranker_client,
        generation_client,
        template_parser,
    ):
        self.retrieval_service = KnowledgeRetrievalService(
            vectordb_client=vectordb_client,
            embedding_client=embedding_client,
            reranker_client=reranker_client,
        )

        self.qa_service = KnowledgeQAService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.summary_service = KnowledgeSummaryService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.key_points_service = KnowledgeKeyPointsService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.notes_service = KnowledgeNotesService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.flashcards_service = KnowledgeFlashcardsService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

        self.quiz_service = KnowledgeQuizService(
            retrieval_service=self.retrieval_service,
            generation_client=generation_client,
            template_parser=template_parser,
        )

    # =========================================================
    # Source Grounding
    # =========================================================

    @staticmethod
    def _build_sources(documents):

        sources = []

        if not documents:
            return sources

        for document in documents:

            metadata = getattr(
                document,
                "metadata",
                None,
            )

            if not isinstance(metadata, dict):
                metadata = {}

            chunk_id = getattr(
                document,
                "chunk_id",
                None,
            )

            score = getattr(
                document,
                "score",
                None,
            )

            source = metadata.get("source")
            page = metadata.get("page")

            source_item = {
                "chunk_id": chunk_id,
                "source": source,
                "page": page,
                "score": score,
            }

            sources.append(source_item)

        return sources

    @classmethod
    def _attach_sources(cls, result):

        if not isinstance(result, dict):
            return result

        documents = result.get("documents", [])

        result["sources"] = cls._build_sources(
            documents=documents
        )

        return result

    # =========================================================
    # QA
    # =========================================================

    async def answer(
        self,
        project,
        query: str,
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.qa_service.answer(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)

    # =========================================================
    # Summary
    # =========================================================

    async def summarize(
        self,
        project,
        query: str,
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.summary_service.summarize(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)

    # =========================================================
    # Key Points
    # =========================================================

    async def extract_key_points(
        self,
        project,
        query: str,
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.key_points_service.extract(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)

    # =========================================================
    # Notes
    # =========================================================

    async def create_notes(
        self,
        project,
        query: str = "",
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.notes_service.create_notes(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)

    # =========================================================
    # Flashcards
    # =========================================================

    async def generate_flashcards(
        self,
        project,
        query: str,
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.flashcards_service.generate(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)

    # =========================================================
    # Quiz
    # =========================================================

    async def generate_quiz(
        self,
        project,
        query: str,
        limit=10,
        top_k=5,
        max_output_tokens=None,
        temperature=None,
    ):
        result = await self.quiz_service.generate(
            project=project,
            query=query,
            limit=limit,
            top_k=top_k,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )

        return self._attach_sources(result)