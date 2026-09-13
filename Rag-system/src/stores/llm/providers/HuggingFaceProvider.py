from ..LLMInterface import LLMInterface
from ..LLMEnums import HuggingFaceEnums, DocumentTypeEnum
from sentence_transformers import SentenceTransformer
import logging
import numpy as np
from typing import List, Union    

class HuggingFaceProvider(LLMInterface):

    def __init__(self, api_key: str = None,
                       default_input_max_characters: int=1000,
                       default_generation_max_output_tokens: int=1000,
                       default_generation_temperature: float=0.1):

        # For HuggingFace, we don't need an API key for local models
        # but we keep the parameter for consistency with the interface
        self.api_key = api_key

        self.default_input_max_characters = default_input_max_characters
        self.default_generation_max_output_tokens = default_generation_max_output_tokens
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = None  # Will be initialized when setting embedding model

        self.enums = HuggingFaceEnums
        self.logger = logging.getLogger("HuggingFaceProvider")

    def set_generation_model(self, model_id: str):
        # HuggingFace provider is for embeddings only, so generation is not supported
        self.generation_model_id = model_id
        # self.logger.warning("HuggingFace provider is for text embeddings only. Generation model set but will not be used for generation.")

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

        # Initialize the SentenceTransformer model
        try:
            self.client = SentenceTransformer(model_id,device='cpu')  # You can change 'cpu' to 'cuda' if you have a GPU available
            self.logger.info(f"HuggingFace embedding model '{model_id}' loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load HuggingFace embedding model '{model_id}': {e}")
            self.client = None

    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()

    def generate_text(self, prompt: str, chat_history: list=[], max_output_tokens: int=None,
                            temperature: float = None):
        # HuggingFace provider is for embeddings only, so generation is not supported
        self.logger.error("HuggingFace provider does not support text generation")
        return None

    def embed_text(self, text: Union[str, List[str]], document_type: str = None):

        if not self.client:
            self.logger.error("HuggingFace client was not set")
            return None

        if isinstance(text, str):
            text = [text]

        if not self.embedding_model_id:
            self.logger.error("Embedding model for HuggingFace was not set")
            return None

        try:
            processed_text = [
                self.process_text(t)
                for t in text
            ]

            embeddings = self.client.encode(
                processed_text,
                convert_to_numpy=True
            )

            return embeddings.tolist()

        except Exception as e:
            self.logger.error(
                f"Error while embedding text with HuggingFace: {e}"
            )
            return None

    def construct_prompt(self, prompt: str, role: str):
            return {
                "role": role,
                "text": prompt,
            }