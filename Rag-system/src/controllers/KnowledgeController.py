from services.knowledge import (
    KnowledgeRetrievalService, KnowledgeQAService, KnowledgeSummaryService,
    KnowledgeKeyPointsService, KnowledgeNotesService, KnowledgeFlashcardsService, 
    KnowledgeQuizService, KnowledgeFAQService, KnowledgeMindMapService
)

class KnowledgeController:
    def __init__(self, db_client, vectordb_client, embedding_client, reranker_client, generation_client, template_parser):
        self.db_client = db_client
        self.retrieval_service = KnowledgeRetrievalService(
            vectordb_client=vectordb_client, embedding_client=embedding_client, reranker_client=reranker_client,
        )
        self.qa_service = KnowledgeQAService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.summary_service = KnowledgeSummaryService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.key_points_service = KnowledgeKeyPointsService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.notes_service = KnowledgeNotesService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.flashcards_service = KnowledgeFlashcardsService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.quiz_service = KnowledgeQuizService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.faq_service = KnowledgeFAQService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)
        self.mindmap_service = KnowledgeMindMapService(retrieval_service=self.retrieval_service, generation_client=generation_client, template_parser=template_parser)

    @staticmethod
    def _build_sources(documents):
        sources = []
        if not documents: return sources
        for document in documents:
            metadata = getattr(document, "metadata", None) or {}
            sources.append({"chunk_id": getattr(document, "chunk_id", None), "source": metadata.get("source"), "page": metadata.get("page"), "score": getattr(document, "score", None)})
        return sources

    @classmethod
    def _attach_sources(cls, result):
        if not isinstance(result, dict): return result
        result["sources"] = cls._build_sources(result.get("documents", []))
        return result

    # 👇 شيلنا الـ limit والـ top_k من كل الدوال هنا

    async def answer(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.qa_service.answer(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def summarize(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.summary_service.summarize(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def extract_key_points(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.key_points_service.extract(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def create_notes(self, db_client, project, query="", file_id=None, max_output_tokens=None, temperature=None):
        res = await self.notes_service.create_notes(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def generate_flashcards(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.flashcards_service.generate(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def generate_quiz(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.quiz_service.generate(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def generate_faq(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.faq_service.generate(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)

    async def generate_mindmap(self, db_client, project, query, file_id=None, max_output_tokens=None, temperature=None):
        res = await self.mindmap_service.generate(db_client=db_client, file_id=file_id, project=project, query=query, max_output_tokens=max_output_tokens, temperature=temperature)
        return self._attach_sources(res)