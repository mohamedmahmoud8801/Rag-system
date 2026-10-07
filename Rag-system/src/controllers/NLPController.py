from helpers.config import get_settings

from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum,OpenAIEnums, CoHereEnums
from typing import List
import json
from models.ChunkModel import ChunkModel
from .ProcessController import ProcessController
import os
import base64

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, 
                 embedding_client,reranker_client ,template_parser):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.reranker_client = reranker_client
        self.template_parser = template_parser
        self.process_controller = None
        self.vlm_client = None

    def query_requires_visual_analysis(self, query: str) -> bool:
        visual_keywords = [
            "أين",
            "مكان",
            "يظهر",
            "شكل",
            "صورة",
            "الصورة",
            "جدول",
            "مخطط",
            "رسم",
            "لون",
            "ختم",
            "توقيع",
            "شعار",
            "أعلى",
            "أسفل",
            "يمين",
            "يسار",
            "where",
            "location",
            "appears",
            "image",
            "picture",
            "table",
            "chart",
            "diagram",
            "color",
            "signature",
            "logo",
            "top",
            "bottom",
            "left",
            "right",
        ]

        query_lower = query.lower()

        return any(
            keyword.lower() in query_lower
            for keyword in visual_keywords
        )

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
    
    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name=collection_name)

        return json.loads(
            json.dumps(collection_info, default=lambda x: x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                                   chunks_ids: List[int], 
                                   do_reset: bool = False):
        
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [ c.chunk_text for c in chunks ]
        metadata = [ c.chunk_metadata for c in  chunks]
        # ===================== DEBUG =====================

        print("\n========== INDEX DEBUG ==========")
        print("chunks:", len(chunks))
        print("chunk_ids:", chunks_ids)
        print("texts type:", type(texts))
        print("texts count:", len(texts))

        for i, text in enumerate(texts[:3]):
            print(f"text[{i}] type:", type(text))
            print(f"text[{i}] value:", repr(text[:200] if text else text))

        print("=================================\n")

        vectors = self.embedding_client.embed_text(text=texts, 
                        document_type=DocumentTypeEnum.DOCUMENT.value)

        print("\n========== VIDEO/DOCUMENT EMBEDDING DEBUG ==========")
        print("texts type:", type(texts))
        print("texts len:", len(texts) if texts is not None else None)
        print("first text:", texts[0][:300] if texts else None)
        print("vectors type:", type(vectors))
        print("vectors len:", len(vectors) if vectors is not None else None)
        print("====================================================\n")

        # step3: create collection if not exists
        _ = await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        _ = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        return True

    async def search_vector_db_collection(
        self,
        project: Project,
        text: str,
        limit: int = 10,
        file_id: str = None
):

        # Step 1: get collection name
        query_vector = None
        collection_name = self.create_collection_name(
            project_id=project.project_id
        )

        # Step 2: get text embedding vector
        vectors = self.embedding_client.embed_text(
            text=text,
            document_type=DocumentTypeEnum.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            return False

        if isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]

        if not query_vector:
            return False

        # Step 3: semantic search
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit,
            file_id=file_id
        )

        if not results:
            return False

        # ==============================
        # DEBUG: BEFORE RERANK
        # ==============================
        print("\n========== BEFORE RERANK ==========")

        for i, doc in enumerate(results, 1):
            print(
                f"{i}. chunk_id={doc.chunk_id} "
                f"vector_score={doc.score}"
            )
            print(f"DATA: {doc.model_dump()}")

        # ==============================
        # Step 4: RERANK
        # ==============================
        settings = get_settings()

        if settings.RERANK_ENABLED:
            reranked_results = self.reranker_client.rerank(
                query=text,
                documents=results,
                top_k=settings.FINAL_CONTEXTS
            )
        else:
            reranked_results = results[:settings.FINAL_CONTEXTS]

        # ==============================
        # DEBUG: AFTER RERANK
        # ==============================
        

        print("\n========== AFTER RERANK ==========")

        for i, doc in enumerate(reranked_results, 1):
            print(
                f"{i}. chunk_id={doc.chunk_id} "
                f"vector_score={doc.score} "
                f"rerank_score={doc.rerank_score}"
            )
            print(f"DATA: {doc.model_dump()}")
        if not reranked_results:
            return False

        return reranked_results


    async def enrich_retrieved_documents(self,retrieved_documents,db_client):
        chunk_model = await ChunkModel.create_instance(
            db_client=db_client
        )

        enriched_documents = []

        for document in retrieved_documents:

            if document.chunk_id is None:
                continue

            chunk = await chunk_model.get_chunk(
                chunk_id=document.chunk_id
            )

            if not chunk:
                continue

            asset = chunk.asset

            page = None

            if chunk.chunk_metadata:
                page = chunk.chunk_metadata.get("page")

            enriched_documents.append({
                "text": document.text,
                "score": document.score,
                "chunk_id": document.chunk_id,
                "metadata": document.metadata,
                "asset_id": chunk.chunk_asset_id,
                "file_id": asset.asset_name if asset else None,
                "page": page
            })

        return enriched_documents

    async def prepare_multimodal_documents(self,project: Project,query: str,limit: int,db_client):
        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
            file_id=file_id
        )
       
        enriched_documents = await self.enrich_retrieved_documents(
            retrieved_documents=retrieved_documents,
            db_client=db_client
        )
        print("========== MULTIMODAL DEBUG ==========")
        print("retrieved_documents:", retrieved_documents)
        print("enriched_documents:", enriched_documents)
        print("======================================")

        if self.process_controller is None:
            self.process_controller = ProcessController(
                project_id=project.project_id
            )

        if self.vlm_client is None:
            self.vlm_client = self.process_controller.vlm_client

        for document in enriched_documents:

            file_id = document.get("file_id")
            page = document.get("page")

            if not file_id:
                document["image"] = None
                continue

            file_ext = os.path.splitext(file_id)[-1].lower()

            # ==========================================
            # PDF
            # ==========================================

            if file_ext == ".pdf":

                if not page:
                    document["image"] = None
                    continue

                image_base64 = (
                    self.process_controller
                    .get_pdf_page_image_base64(
                        file_id=file_id,
                        page_number=page
                    )
                )

                document["image"] = image_base64

            # ==========================================
            # Image
            # ==========================================

            elif file_ext in (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp"
            ):

                image_path = os.path.join(
                    self.process_controller.project_path,
                    file_id
                )

                try:

                    with open(image_path, "rb") as image_file:

                        image_bytes = image_file.read()

                    processed_bytes, image_type = (
                        self.process_controller.preprocess_image(
                            image_bytes=image_bytes
                        )
                    )

                    document["image"] = base64.b64encode(
                        processed_bytes
                    ).decode("utf-8")

                except Exception as e:

                    print(
                        f"Error loading image {file_id}: {e}"
                    )

                    document["image"] = None

            else:

                document["image"] = None

        print("========== AFTER IMAGE PREPARATION ==========")

        for i, document in enumerate(enriched_documents):
            print(
                f"Document {i} | "
                f"file_id={document.get('file_id')} | "
                f"image_exists={bool(document.get('image'))}"
            )

        print("==============================================")

        return enriched_documents
    

   
    async def analyze_multimodal_documents(
    self,
    documents,
    query: str):
        results = []

        requires_visual_analysis = self.query_requires_visual_analysis(query)

        print("========== MULTIMODAL QUERY ROUTER ==========")
        print(f"Query: {query}")
        print(f"Visual analysis required: {requires_visual_analysis}")
        print("==============================================")

        # =====================================================
        # Normal question
        # =====================================================

        if not requires_visual_analysis:

            for document in documents:
                results.append({
                    **document,
                    "vlm_analysis": None
                })

            return results

        # =====================================================
        # Default grounding result
        # =====================================================

        def empty_grounding():
            return {
                "found": False,
                "bbox": None,
                "position": None,
                "landmark": None
            }

        # =====================================================
        # Parse VLM response
        # =====================================================

        def parse_grounding_response(raw_result):

            if not raw_result:
                return empty_grounding()

            raw_result = raw_result.strip()

            # -------------------------------------------------
            # 1. Try JSON first
            # -------------------------------------------------

            VALID_POSITIONS = {
                "top-left", "top-center", "top-right",
                "middle-left", "middle-center", "middle-right",
                "bottom-left", "bottom-center", "bottom-right"
            }

            try:

                parsed = json.loads(raw_result)

                if isinstance(parsed, dict):

                    position = parsed.get("position")

                    if position not in VALID_POSITIONS:
                        position = None

                    return {
                        "found": parsed.get("found", False),
                        "bbox": parsed.get("bbox"),
                        "position": position,
                        "landmark": parsed.get("landmark")
                    }

            except json.JSONDecodeError:
                pass
            # -------------------------------------------------
            # 2. Fallback: parse natural language
            # -------------------------------------------------

            text = raw_result.lower()

            # -------------------------------------------------
            # Detect position
            # -------------------------------------------------

            position = None

            position_mapping = {

                "top-left": "top-left",
                "top left": "top-left",

                "top-center": "top-center",
                "top center": "top-center",

                "top-right": "top-right",
                "top right": "top-right",

                "middle-left": "middle-left",
                "middle left": "middle-left",

                "middle-center": "middle-center",
                "middle center": "middle-center",

                "middle-right": "middle-right",
                "middle right": "middle-right",

                "bottom-left": "bottom-left",
                "bottom left": "bottom-left",

                "bottom-center": "bottom-center",
                "bottom center": "bottom-center",

                "bottom-right": "bottom-right",
                "bottom right": "bottom-right"
            }

            for key, value in position_mapping.items():

                if key in text:
                    position = value
                    break

            # -------------------------------------------------
            # Arabic position detection
            # -------------------------------------------------

            if position is None:

                if "الجزء العلوي" in text or "أعلى" in text:
                    position = "top-center"

                elif "الجزء السفلي" in text or "أسفل" in text:
                    position = "bottom-center"

                elif "الجزء الأوسط" in text or "المنتصف" in text:
                    position = "middle-center"

            # -------------------------------------------------
            # Detect whether information was found
            # -------------------------------------------------

            found = True

            not_found_phrases = [
                "not visible",
                "not found",
                "cannot locate",
                "can't locate",
                "not present",
                "غير موجود",
                "غير ظاهر",
                "غير مرئي",
                "لا يظهر",
                "لا يمكن العثور"
            ]

            for phrase in not_found_phrases:

                if phrase in text:
                    found = False
                    break

            # -------------------------------------------------
            # Extract landmark
            # -------------------------------------------------

            landmark = None

            if "below" in text:
                landmark = "below the referenced element"

            elif "above" in text:
                landmark = "above the referenced element"

            elif "right of" in text:
                landmark = "to the right of the referenced element"

            elif "left of" in text:
                landmark = "to the left of the referenced element"

            # -------------------------------------------------
            # If we found visual location information
            # -------------------------------------------------

            if found and position:

                return {
                    "found": True,
                    "bbox": None,
                    "position": position,
                    "landmark": landmark
                }

            return empty_grounding()

        # =====================================================
        # Select image documents
        # =====================================================

        image_documents = [
            document
            for document in documents
            if document.get("image")
        ]

        # Only top 2
        image_documents = image_documents[:2]

        selected_document_ids = {
            document.get("chunk_id")
            for document in image_documents
        }

        print(
            f"[GROUNDING] Images available: "
            f"{len(image_documents)}"
        )

        analyzed_images = {}

        # =====================================================
        # Process documents
        # =====================================================

        for document in documents:

            image_base64 = document.get("image")

            if not image_base64:

                results.append({
                    **document,
                    "vlm_analysis": None
                })

                continue

            if document.get("chunk_id") not in selected_document_ids:

                results.append({
                    **document,
                    "vlm_analysis": None
                })

                continue

            file_id = document.get("file_id")
            page = document.get("page")

            image_key = (file_id, page)

            # =================================================
            # Reuse analysis for same image
            # =================================================

            if image_key in analyzed_images:

                grounding_result = analyzed_images[image_key]

            else:

                # =================================================
                # Simpler grounding prompt
                # =================================================

                prompt = f"""
            You are a visual location detector.

            Look at the document image.

            User question:
            {query}

            Find WHERE the requested information appears in the image.

            IMPORTANT:

            - You MUST inspect the image.
            - Do NOT answer the user's question.
            - Do NOT summarize.
            - Do NOT translate.
            - Do NOT repeat the OCR.
            - ONLY describe the visual location.

            Classify the location into exactly ONE of:

            top-left
            top-center
            top-right

            middle-left
            middle-center
            middle-right

            bottom-left
            bottom-center
            bottom-right

            Also mention the nearest visual landmark.

            OCR is only a hint:

            {document.get("text", "")}

            Return a SHORT answer.

            Example:

            top-center.
            Below the student label.

            Or:

            middle-center.
            Below the student label.

            If the information cannot be found:

            not found.
            """

                try:

                    raw_result = self.vlm_client.analyze_image_base64(
                        image_base64=image_base64,
                        prompt=prompt,
                        image_type="image/jpeg"
                    )

                    print("========== RAW GROUNDING ==========")
                    print(raw_result)
                    print("===================================")

                    grounding_result = parse_grounding_response(
                        raw_result
                    )

                except Exception as e:

                    print(
                        f"[GROUNDING] VLM failed for "
                        f"{file_id}: {e}"
                    )

                    grounding_result = empty_grounding()

                analyzed_images[image_key] = grounding_result

            # =================================================
            # Attach result
            # =================================================

            results.append({
                **document,
                "vlm_analysis": grounding_result
            })

        return results




    async def generate_multimodal_answer(
    self,
    documents,
    query: str
):
        """
        Generate the final answer from retrieved multimodal documents.

        Important:
        - Chunks from the same source file are grouped together.
        - Chunks are ordered by chunk_id so consecutive text can be reconstructed.
        - OCR/text is the primary source for factual answers.
        - Visual grounding is used only for spatial questions.
        """

        # ============================================================
        # 1. Group retrieved chunks by source
        # ============================================================

        source_groups = {}

        for document in documents:

            file_id = document.get("file_id")
            page = document.get("page")

            source_key = (file_id, page)

            if source_key not in source_groups:
                source_groups[source_key] = []

            source_groups[source_key].append(document)

        # ============================================================
        # 2. Build context
        # ============================================================

        context_parts = []

        for (file_id, page), source_documents in source_groups.items():

            # --------------------------------------------------------
            # Sort chunks by chunk_id
            # --------------------------------------------------------

            source_documents = sorted(
                source_documents,
                key=lambda d: (
                    d.get("chunk_id") is None,
                    d.get("chunk_id") or 0
                )
            )

            source_text_parts = []

            for document in source_documents:

                text = document.get("text", "")
                chunk_id = document.get("chunk_id")

                if not text:
                    continue

                source_text_parts.append(
                    f"[Chunk {chunk_id}]\n{text.strip()}"
                )

            if not source_text_parts:
                continue

            # --------------------------------------------------------
            # Combine chunks belonging to the same source
            # --------------------------------------------------------

            combined_text = "\n\n".join(source_text_parts)

            source_context = f"""
    Source File:
    {file_id}

    Page:
    {page}

    Retrieved Content:
    {combined_text}
    """

            context_parts.append(source_context)

        # ============================================================
        # 3. Add visual grounding separately
        # ============================================================

        seen_visual_sources = set()

        visual_parts = []

        for document in documents:

            grounding = document.get("vlm_analysis")

            if not grounding:
                continue

            file_id = document.get("file_id")
            page = document.get("page")

            visual_key = (file_id, page)

            if visual_key in seen_visual_sources:
                continue

            visual_parts.append(
                f"""
    Visual Grounding:
    Source File: {file_id}
    Page: {page}

    {json.dumps(
        grounding,
        ensure_ascii=False,
        indent=2
    )}
    """
            )

            seen_visual_sources.add(visual_key)

        # ------------------------------------------------------------
        # Add visual information only if available
        # ------------------------------------------------------------

        if visual_parts:
            context_parts.extend(visual_parts)

        # ============================================================
        # 4. Final context
        # ============================================================

        context = "\n\n==============================\n\n".join(
            context_parts
        )

        # ============================================================
        # 5. System prompt
        # ============================================================

        system_prompt = """
    You are an AI assistant answering questions using retrieved
    documents from a multimodal RAG system.

    Rules:

    1. Answer only using the provided context.

    2. Retrieved chunks may be consecutive parts of the same
    document, paragraph, sentence, or text block.

    3. Chunks from the same source file are intentionally grouped
    together. Read them as a continuous document when appropriate.

    4. If a sentence starts in one chunk and continues in another
    chunk, combine the chunks to understand the complete sentence.

    5. OCR text may contain minor recognition errors.
    If the intended wording is obvious from the surrounding
    context, you may normalize obvious OCR errors.

    6. Do not invent information that is not supported by the
    provided context.

    7. For questions asking for text, names, numbers, dates,
    qualifications, or document facts, use the OCR/retrieved
    text as the primary source.

    8. Visual grounding is only for determining where something
    appears in an image.

    9. If the user asks where an element appears and visual
    grounding provides a position or bounding box, use that
    information.

    10. Do not mention:
        - embeddings
        - vector databases
        - chunks
        - similarity scores
        - retrieval
        - VLM
        - internal processing

    11. Answer in the same language as the user's question.

    12. Be concise and direct.

    13. If the requested information genuinely cannot be found
        in the provided context, say:

        "The answer is not available in the provided documents."
    """

        # ============================================================
        # 6. User prompt
        # ============================================================

        full_prompt = f"""
    Retrieved Context:

    {context}

    ==============================

    User Question:
    {query}

    ==============================

    Answer:
    """

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value
            )
        ]

        # ============================================================
        # 7. Generate answer
        # ============================================================

        try:

            answer = self.generation_client.generate_text(
                prompt=full_prompt,
                chat_history=chat_history
            )

            return answer

        except Exception as e:

            print(
                f"Multimodal final answer generation failed: {e}"
            )

            return None
    async def answer_rag_question(
        self,
        project: Project,
        query: str,
        limit: int = 10,
        return_contexts: bool = False,
        file_id: str = None,
    ):
        answer, full_prompt, chat_history = None, None, None

        # step1: retrieve related documents
        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
            file_id=file_id
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            if return_contexts:
                return answer, full_prompt, chat_history, []
            return answer, full_prompt, chat_history

        

        # step2: Construct LLM prompt
        system_prompt = self.template_parser.get(
            "rag",
            "system_prompt"
        )

        documents_prompts = "\n".join([
            self.template_parser.get(
                "rag",
                "document_prompt",
                {
                    "doc_num": idx + 1,
                    "chunk_text": self.generation_client.process_text(doc.text),
                }
            )
            for idx, doc in enumerate(retrieved_documents)
        ])

        footer_prompt = self.template_parser.get(
            "rag",
            "footer_prompt",
            {
                "query": query
            }
        )

        # step3: Construct Generation Client Prompts
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([
            documents_prompts,
            footer_prompt
        ])

        # step4: Retrieve the Answer
        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        if return_contexts:
            contexts = [
                doc.text
                for doc in retrieved_documents
                if getattr(doc, "text", None)
            ]

            return answer, full_prompt, chat_history, contexts

        return answer, full_prompt, chat_history