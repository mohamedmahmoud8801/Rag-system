from .OCREnums import OCREnums
from .providers.PaddleOCRProvider import PaddleOCRProvider


class OCRProviderFactory:

    def __init__(self, config):
        self.config = config

    def create(self, provider: str):

        provider = provider.lower()

        if provider == OCREnums.PADDLEOCR.value:
            return PaddleOCRProvider(config=self.config)

        return None