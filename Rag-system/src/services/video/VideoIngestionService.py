from typing import List, Dict, Any

from controllers.ProcessController import Document
from models.db_schemes import Asset, DataChunk
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel


class VideoIngestionService:

    def __init__(
        self,
        video_model,
        db_client,
    ):
        self.video_model = video_model
        self.db_client = db_client

    def chunk_transcript(
        self,
        transcript: List[Dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[Document]:

        if not transcript:
            return []

        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        documents = []

        current_segments = []
        current_length = 0

        for segment in transcript:

            text = (segment.get("text") or "").strip()

            if not text:
                continue

            start_time = float(
                segment.get("start_time", 0.0)
            )

            end_time = float(
                segment.get("end_time", start_time)
            )

            segment_length = len(text)

            # --------------------------------------------------
            # If the current chunk would exceed the limit,
            # finalize it first.
            # --------------------------------------------------

            if (
                current_segments
                and current_length + segment_length + 1 > chunk_size
            ):

                documents.append(
                    self._build_document(
                        segments=current_segments
                    )
                )

                # --------------------------------------------------
                # Keep overlapping transcript content.
                # We keep the latest segments until their combined
                # text length reaches the requested overlap.
                # --------------------------------------------------

                overlap_segments = []
                overlap_length = 0

                for previous_segment in reversed(current_segments):

                    previous_text = (
                        previous_segment["text"].strip()
                    )

                    previous_length = len(previous_text)

                    if (
                        overlap_length + previous_length
                        > chunk_overlap
                    ):
                        break

                    overlap_segments.insert(
                        0,
                        previous_segment
                    )

                    overlap_length += previous_length + 1

                current_segments = overlap_segments

                current_length = sum(
                    len(item["text"].strip()) + 1
                    for item in current_segments
                )

            current_segments.append(
                {
                    "text": text,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )

            current_length += segment_length + 1

        # --------------------------------------------------
        # Final chunk
        # --------------------------------------------------

        if current_segments:

            documents.append(
                self._build_document(
                    segments=current_segments
                )
            )

        return documents

    def _build_document(
        self,
        segments: List[Dict[str, Any]],
    ) -> Document:

        text = " ".join(
            segment["text"].strip()
            for segment in segments
            if segment.get("text")
        ).strip()

        start_time = float(
            segments[0]["start_time"]
        )

        end_time = float(
            segments[-1]["end_time"]
        )

        return Document(
            page_content=text,
            metadata={
                "start_time": start_time,
                "end_time": end_time,
            },
        )

    def _build_asset(
        self,
        project_id: int,
        video_data: Dict[str, Any],
        provider: str,
        language: str | None,
    ) -> Asset:

        video_id = video_data["video_id"]
        video_url = video_data["video_url"]

        return Asset(
            asset_type="video",
            asset_name=f"{provider}_{video_id}",
            asset_size=0,
            asset_config={
                "provider": provider,
                "video_id": video_id,
                "video_url": video_url,
                "language": language,
                "duration": video_data.get("duration"),
                "transcript_segments": video_data.get(
                    "transcript_segments",
                    0,
                ),
            },
            asset_project_id=project_id,
        )

    def _build_chunks(
        self,
        documents: List[Document],
        project_id: int,
        asset_id: int,
        video_data: Dict[str, Any],
        provider: str,
        language: str | None,
    ) -> List[DataChunk]:

        video_id = video_data["video_id"]
        video_url = video_data["video_url"]

        chunks = []

        for index, document in enumerate(
            documents,
            start=1,
        ):

            metadata = {
                "source_type": "video",
                "video_provider": provider,
                "video_id": video_id,
                "video_url": video_url,
                "language": language,
                "start_time": document.metadata.get(
                    "start_time"
                ),
                "end_time": document.metadata.get(
                    "end_time"
                ),
                "extraction_method": "youtube_transcript",
            }

            chunks.append(
                DataChunk(
                    chunk_text=document.page_content,
                    chunk_metadata=metadata,
                    chunk_order=index,
                    chunk_project_id=project_id,
                    chunk_asset_id=asset_id,
                )
            )

        return chunks

    async def ingest(
        self,
        project_id: int,
        video_url: str,
        provider: str,
        language: str | None,
        chunk_size: int,
        chunk_overlap: int,
    ):

        # --------------------------------------------------
        # 1. Get video + transcript
        # --------------------------------------------------

        video_data = await self.video_model.get_video(
            video_url=video_url,
            language=language,
        )

        if not video_data:
            raise ValueError(
                "Could not retrieve video data."
            )

        transcript = video_data.get(
            "transcript",
            []
        )

        if not transcript:
            raise ValueError(
                "No transcript was found for this video."
            )

        # --------------------------------------------------
        # 2. Timestamp-aware chunking
        # --------------------------------------------------

        documents = self.chunk_transcript(
            transcript=transcript,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not documents:
            raise ValueError(
                "No chunks were generated from the transcript."
            )

        # --------------------------------------------------
        # 3. Create Asset
        # --------------------------------------------------

        asset_model = await AssetModel.create_instance(
            db_client=self.db_client
        )

        asset = self._build_asset(
            project_id=project_id,
            video_data=video_data,
            provider=provider,
            language=language,
        )

        asset = await asset_model.create_asset(
            asset=asset
        )

        # --------------------------------------------------
        # 4. Create DataChunks
        # --------------------------------------------------

        chunk_model = await ChunkModel.create_instance(
            db_client=self.db_client
        )

        chunks = self._build_chunks(
            documents=documents,
            project_id=project_id,
            asset_id=asset.asset_id,
            video_data=video_data,
            provider=provider,
            language=language,
        )

        await chunk_model.insert_many_chunks(
            chunks=chunks
        )

        # --------------------------------------------------
        # 5. Return everything required by the controller
        # --------------------------------------------------

        return {
            "video": video_data,
            "asset": asset,
            "chunks": chunks,
            "documents": documents,
        }