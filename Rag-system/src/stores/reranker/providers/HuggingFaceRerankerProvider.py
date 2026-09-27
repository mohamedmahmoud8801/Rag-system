from ..RerankerInterface import RerankerInterface

from sentence_transformers import CrossEncoder

import logging
from typing import List


class HuggingFaceRerankerProvider(RerankerInterface):

    def __init__(
        self,
        default_model_id: str = "BAAI/bge-reranker-v2-m3",
        max_length: int = 512,
    ):
        self.model_id = None
        self.client = None
        self.max_length = max_length

        self.logger = logging.getLogger("HuggingFaceRerankerProvider")

        self.set_model(default_model_id)

    def set_model(self, model_id: str):

        self.model_id = model_id

        try:

            self.client = CrossEncoder(
                model_id,
                max_length=self.max_length,
                device="cpu"
            )

            self.logger.info(
                f"HuggingFace reranker model "
                f"'{model_id}' loaded successfully"
            )

        except Exception as e:

            self.logger.error(
                f"Failed to load HuggingFace reranker "
                f"model '{model_id}': {e}"
            )

            self.client = None

    def rerank(
        self,
        query: str,
        documents: List,
        top_k: int = 5
    ):

        if not self.client:

            self.logger.error(
                "HuggingFace reranker client was not initialized"
            )

            return documents[:top_k]

        if not documents:

            return []

        try:

            pairs = [
                [query, document.text]
                for document in documents
            ]

            scores = self.client.predict(
                pairs,
                convert_to_numpy=True
            )

            reranked_documents = []

            for document, score in zip(documents, scores):

                document.rerank_score = float(score)

                reranked_documents.append(
                    document
                )

            reranked_documents.sort(
                key=lambda document: document.rerank_score,
                reverse=True
            )

            return reranked_documents[:top_k]

        except Exception as e:

            self.logger.error(
                f"Error while reranking documents: {e}"
            )

            return documents[:top_k]