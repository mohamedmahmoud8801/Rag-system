from .RerankerEnums import RerankerEnums
from .providers.HuggingFaceRerankerProvider import (
    HuggingFaceRerankerProvider
)


class RerankerProviderFactory:

    @staticmethod
    def create(
        provider: str,
        model_id: str
    ):

        if provider == RerankerEnums.HUGGINGFACE.value:

            return HuggingFaceRerankerProvider(
                default_model_id=model_id
            )

        raise ValueError(
            f"Unsupported reranker provider: {provider}"
        )