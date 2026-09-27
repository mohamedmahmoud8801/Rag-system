from .VLMEnums import VLMEnums
from .providers import OllamaVLMProvider


class VLMProviderFactory:

    def __init__(self, config):

        self.config = config

    def create(self, provider: str):

        provider = provider.lower()

        if provider == VLMEnums.OLLAMA.value:

            return OllamaVLMProvider(
                config=self.config
            )

        return None