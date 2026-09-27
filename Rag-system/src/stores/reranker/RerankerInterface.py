from abc import ABC, abstractmethod
from typing import List


class RerankerInterface(ABC):

    @abstractmethod
    def set_model(self, model_id: str):
        pass

    @abstractmethod
    def rerank(self, query: str, documents: List, top_k: int = 5):
        pass