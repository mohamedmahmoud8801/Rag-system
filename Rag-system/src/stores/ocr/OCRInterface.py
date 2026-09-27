from abc import ABC, abstractmethod


class OCRInterface(ABC):

    @abstractmethod
    def extract_text(
        self,
        image_base64: str,
        image_type: str = "image/png"
    ):
        pass