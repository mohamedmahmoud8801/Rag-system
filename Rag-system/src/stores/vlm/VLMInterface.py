from abc import ABC, abstractmethod


class VLMInterface(ABC):

    @abstractmethod
    def set_generation_model(self, model_id: str):
        pass

    @abstractmethod
    def analyze_image(
        self,
        image_path: str,
        prompt: str,
        max_output_tokens: int = None,
        temperature: float = None
    ):
        pass

    @abstractmethod
    def analyze_image_base64(
        self,
        image_base64: str,
        prompt: str,
        image_type: str = "image/jpeg",
        max_output_tokens: int = None,
        temperature: float = None
    ):
        pass