from models.db_schemes import Project
from stores.llm.LLMEnums import DocumentTypeEnum
from models.ChunkModel import ChunkModel
from models.AssetModel import AssetModel
from models.db_schemes import RetrievedDocument

class KnowledgeRetrievalService:
    def __init__(self, vectordb_client, embedding_client, reranker_client):
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.reranker_client = reranker_client

    def create_collection_name(self, project_id: int) -> str:
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    async def retrieve(self, project, query, file_id=None, db_client=None):
        # 👇 1. لو في file_id، بنجيب كل الـ chunks من الداتابيز مباشرة من غير أي limit
        if file_id and db_client:
            asset_model = await AssetModel.create_instance(db_client=db_client)
            asset = await asset_model.get_asset_record(project.project_id, file_id)
            if not asset:
                return []
            
            chunk_model = await ChunkModel.create_instance(db_client=db_client)
            chunks = await chunk_model.get_chunks_by_asset_id(asset.asset_id)
            
            docs = []
            for c in chunks:
                docs.append(RetrievedDocument(
                    text=c.chunk_text,
                    chunk_id=c.chunk_id,
                    metadata=c.chunk_metadata,
                    score=1.0
                ))
            return docs # 👈 بيرجع كل الفيديو كله بدون أي قص
            
        # 👇 2. البحث بالـ Vector لو مفيش file_id (هنا بنجيب 10 نتائج بحث بس)
        query_vector = self.embedding_client.embed_text(text=query, document_type=DocumentTypeEnum.QUERY.value)[0]
        collection_name = self.create_collection_name(project_id=project.project_id)
        results = await self.vectordb_client.search_by_vector(collection_name=collection_name, vector=query_vector, limit=10)
        
        return results or []