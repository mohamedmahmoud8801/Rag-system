from ..LLMInterface import LLMInterface
from ..LLMEnums import HuggingFaceEnums, DocumentTypeEnum
from sentence_transformers import SentenceTransformer

import logging
from typing import List, Union


class HuggingFaceProvider(LLMInterface):

    def __init__(
        self,
        api_key: str = None,
        default_input_max_characters: int = 1000,
        default_generation_max_output_tokens: int = 1000,
        default_generation_temperature: float = 0.1,
    ):

        # HuggingFace/SentenceTransformer is used locally for embeddings.
        # api_key is kept for interface consistency.
        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = (
            default_generation_max_output_tokens
        )
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = None

        self.enums = HuggingFaceEnums
        self.logger = logging.getLogger("HuggingFaceProvider")

    def set_generation_model(self, model_id: str):
        # HuggingFace provider is used for embeddings only.
        self.generation_model_id = model_id

    def set_embedding_model(
        self,
        model_id: str,
        embedding_size: int
    ):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

        try:
            self.client = SentenceTransformer(
                model_id,
                device="cpu"
            )

            self.logger.info(
                f"HuggingFace embedding model "
                f"'{model_id}' loaded successfully"
            )

        except Exception:
            self.logger.exception(
                f"Failed to load HuggingFace embedding model "
                f"'{model_id}'"
            )
            self.client = None

    def process_text(self, text: str):
        if text is None:
            return ""

        return text[:self.default_input_max_characters].strip()

    def generate_text(
        self,
        prompt: str,
        chat_history: list = [],
        max_output_tokens: int = None,
        temperature: float = None
    ):
        # HuggingFace provider is for embeddings only.
        self.logger.error(
            "HuggingFace provider does not support text generation"
        )
        return None

    def embed_text(
    self,
    text: Union[str, List[str]],
    document_type: str = None
):

        if not self.client:
            self.logger.error("HuggingFace client was not set")
            return None

        if isinstance(text, str):
            text = [text]

        if not self.embedding_model_id:
            self.logger.error(
                "Embedding model for HuggingFace was not set"
            )
            return None

        try:
            prefix = (
                "query: "
                if document_type == DocumentTypeEnum.QUERY.value
                else "passage: "
            )

            processed_text = [
                prefix + self.process_text(t)
                for t in text
            ]

            embeddings = self.client.encode(
                processed_text,
                convert_to_numpy=True
            )

            return embeddings.tolist()

        except Exception:
            self.logger.exception(
                "Error while embedding text with HuggingFace"
            )
            return None

    def construct_prompt(
        self,
        prompt: str,
        role: str
    ):
        return {
            "role": role,
            "text": prompt,
        }