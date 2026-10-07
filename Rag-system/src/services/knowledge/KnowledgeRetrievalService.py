from models.db_schemes import Project
from stores.llm.LLMEnums import DocumentTypeEnum


class KnowledgeRetrievalService:

    def __init__(
        self,
        vectordb_client,
        embedding_client,
        reranker_client,
    ):
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.reranker_client = reranker_client

    def create_collection_name(
        self,
        project_id: int,
    ) -> str:

        return (
            f"collection_"
            f"{self.vectordb_client.default_vector_size}_"
            f"{project_id}"
        ).strip()

    async def retrieve(
        self,
        project: Project,
        query: str,
        limit: int = 10,
        top_k: int = 5,
    ):

        if not query or not query.strip():
            return []

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero."
            )

        collection_name = self.create_collection_name(
            project_id=project.project_id
        )

        vectors = self.embedding_client.embed_text(
            text=query,
            document_type=DocumentTypeEnum.QUERY.value,
        )

        if not vectors:
            return []

        query_vector = vectors[0]

        if not query_vector:
            return []

        retrieved_documents = (
            await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=query_vector,
                limit=limit,
            )
        )

        if not retrieved_documents:
            return []

        reranked_documents = self.reranker_client.rerank(
            query=query,
            documents=retrieved_documents,
            top_k=top_k,
        )

        if not reranked_documents:
            return []

        return reranked_documents