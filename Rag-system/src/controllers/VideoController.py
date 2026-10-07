from controllers.NLPController import NLPController
from models.ProjectModel import ProjectModel
from services.video.VideoIngestionService import VideoIngestionService
from models.VideoModel import VideoModel
from stores.video.VideoProviderFactory import VideoProviderFactory


class VideoController:

    def __init__(
        self,
        db_client,
        vectordb_client,
        embedding_client,
        generation_client,
        reranker_client,
        template_parser,
    ):

        self.db_client = db_client
        self.vectordb_client = vectordb_client
        self.embedding_client = embedding_client
        self.generation_client = generation_client
        self.reranker_client = reranker_client
        self.template_parser = template_parser

    def create_collection_name(
        self,
        project_id: int,
    ) -> str:

        return (
            f"collection_"
            f"{self.vectordb_client.default_vector_size}_"
            f"{project_id}"
        ).strip()

    async def ingest_video(
        self,
        project_id: int,
        video_url: str,
        provider: str = "youtube",
        language: str | None = None,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
    ):

        # --------------------------------------------------
        # 1. Get/Create Project
        # --------------------------------------------------

        project_model = await ProjectModel.create_instance(
            db_client=self.db_client
        )

        project = await project_model.get_project_or_create_one(
            project_id=project_id
        )

        # --------------------------------------------------
        # 2. Create Video Provider
        # --------------------------------------------------

        video_provider = VideoProviderFactory.create(
            provider=provider
        )

        # --------------------------------------------------
        # 3. Wrap provider in VideoModel
        # --------------------------------------------------

        video_model = await VideoModel.create_instance(
            provider=video_provider
        )

        # --------------------------------------------------
        # 4. Video ingestion
        # --------------------------------------------------

        ingestion_service = VideoIngestionService(
            video_model=video_model,
            db_client=self.db_client,
        )

        ingestion_result = await ingestion_service.ingest(
            project_id=project.project_id,
            video_url=video_url,
            provider=provider,
            language=language,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunks = ingestion_result["chunks"]

        # --------------------------------------------------
        # 5. Existing NLP / Vector pipeline
        # --------------------------------------------------

        nlp_controller = NLPController(
            vectordb_client=self.vectordb_client,
            generation_client=self.generation_client,
            embedding_client=self.embedding_client,
            reranker_client=self.reranker_client,
            template_parser=self.template_parser,
        )

        collection_name = self.create_collection_name(
            project_id=project.project_id
        )

        chunk_ids = [
            chunk.chunk_id
            for chunk in chunks
        ]

        # --------------------------------------------------
        # IMPORTANT:
        # Do NOT reset the shared project collection.
        #
        # PDF / Excel / Image / TXT / Video all use the
        # same project vector collection.
        # --------------------------------------------------

        await nlp_controller.index_into_vector_db(
            project=project,
            chunks=chunks,
            chunks_ids=chunk_ids,
            do_reset=False,
        )

        video_data = ingestion_result["video"]
        asset = ingestion_result["asset"]

        return {
            "success": True,
            "video_id": video_data["video_id"],
            "video_url": video_data["video_url"],
            "provider": provider,
            "source_type": "video",
            "language": language,
            "duration": video_data.get("duration"),
            "transcript_segments": video_data.get(
                "transcript_segments",
                0,
            ),
            "asset_id": asset.asset_id,
            "asset_name": asset.asset_name,
            "chunks_created": len(chunks),
            "chunk_ids": chunk_ids,
            "collection_name": collection_name,
        }