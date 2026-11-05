from ..VLMInterface import VLMInterface
from ..VLMEnums import VLMEnums
from helpers.config import Settings
from openai import OpenAI

import base64
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image
import re


class OllamaVLMProvider(VLMInterface):

    def __init__(self, config: Settings):

        self.config = config

        self.api_key = config.OLLAMA_API_KEY
        self.api_url = config.OLLAMA_API_URL
        self.num_ctx = config.OLLAMA_NUM_CTX

        self.default_input_max_characters = (
            config.INPUT_DEFAULT_MAX_CHARACTERS
        )

        self.default_generation_max_output_tokens = (
            config.VLM_DEFAULT_MAX_OUTPUT_TOKENS
        )
        self.num_ctx = (
            config.OLLAMA_NUM_CTX
        )
        self.default_generation_temperature = (
            config.VLM_DEFAULT_TEMPERATURE
        )

        self.generation_model_id = None

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_url
        )

        self.enums = VLMEnums
        self.logger = logging.getLogger(__name__)

    # =========================================================
    # Model
    # =========================================================

    def set_generation_model(self, model_id: str):

        self.generation_model_id = model_id

    # =========================================================
    # Text Processing
    # =========================================================

    def process_text(self, text: str):

        return text[
            :self.default_input_max_characters
        ].strip()

    # =========================================================
    # Analyze Image From Path
    # =========================================================

    def analyze_image(
        self,
        image_path: str,
        prompt: str,
        max_output_tokens: int = None,
        temperature: float = None
    ):

        if not self.client:

            self.logger.error(
                "Ollama VLM client was not set"
            )

            return None

        if not self.generation_model_id:

            self.logger.error(
                "VLM generation model was not set"
            )

            return None

        try:

            image_base64 = self._image_to_base64(
                image_path
            )

            return self.analyze_image_base64(
                image_base64=image_base64,
                prompt=prompt,
                image_type="image/png",
                max_output_tokens=max_output_tokens,
                temperature=temperature
            )

        except Exception as e:

            self.logger.error(
                f"Error while processing image: {e}"
            )

            return None

    # =========================================================
    # Analyze Image From Base64
    # =========================================================

    def analyze_image_base64(
        self,
        image_base64: str,
        prompt: str,
        image_type: str = "image/png",
        max_output_tokens: int = None,
        temperature: float = None
    ):

        if not self.client:

            self.logger.error(
                "Ollama VLM client was not set"
            )

            return None

        if not self.generation_model_id:

            self.logger.error(
                "VLM generation model was not set"
            )

            return None

        max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else self.default_generation_max_output_tokens
        )

        temperature = (
            temperature
            if temperature is not None
            else self.default_generation_temperature
        )

        try:
            print("========== VLM DEBUG ==========")
            print("MODEL:", self.generation_model_id)
            print("NUM_CTX:", self.num_ctx)
            print("MAX_OUTPUT:", max_output_tokens)
            print("===============================")

            response = self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.process_text(prompt)
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=max_output_tokens,
                temperature=temperature,
                extra_body={
                    "options": {
                        "num_ctx": self.num_ctx,
                        "repeat_penalty":1.2,
                        "repeat_last_n":256,
                        "top_p":0.8,
                        "num_predict":max_output_tokens
                        # "frequency_penalty": 0.6,
                    }
                }
            )
           
            if (
                not response
                or not response.choices
                or len(response.choices) == 0
                or not response.choices[0].message
            ):

                self.logger.error(
                    "Error while analyzing image with Ollama VLM"
                )

                return None

            raw_content = response.choices[0].message.content

            cleaned_content = self._clean_repetition(raw_content)

            if cleaned_content != raw_content:
                self.logger.warning(
                    "Detected and removed degenerate repetition in VLM output"
                )

            return cleaned_content
        except Exception as e:

            self.logger.error(
                f"Error while analyzing image with Ollama VLM: {e}"
            )

            return None

    # =========================================================
    # Convert Any Supported Image To PNG Base64
    # =========================================================

    def _image_to_base64(
        self,
        image_path: str
    ):

        image_path = Path(image_path)

        if not image_path.exists():

            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        try:

            with Image.open(image_path) as image:

                # -------------------------------------------------
                # Animated images
                # -------------------------------------------------

                if getattr(
                    image,
                    "is_animated",
                    False
                ):

                    image.seek(0)

                # -------------------------------------------------
                # Handle image modes
                # -------------------------------------------------

                if image.mode not in (
                    "RGB",
                    "RGBA"
                ):

                    image = image.convert(
                        "RGBA"
                    )

                # -------------------------------------------------
                # Convert to PNG
                # -------------------------------------------------

                buffer = BytesIO()

                image.save(
                    buffer,
                    format="PNG"
                )

                image_bytes = buffer.getvalue()

                # -------------------------------------------------
                # Encode Base64
                # -------------------------------------------------

                image_base64 = base64.b64encode(
                    image_bytes
                ).decode("utf-8")

                return image_base64

        except Exception as e:

            raise ValueError(
                f"Could not process image "
                f"{image_path}: {e}"
            )



    def _clean_repetition(self, text: str, max_repeats: int = 2) -> str:
        """
        Detects and removes degenerate repetition (same line repeated
        many times in a row), which can happen with small VLM models.
        """

        if not text:
            return text

        lines = text.split("\n")
        cleaned_lines = []
        last_line = None
        repeat_count = 0

        for line in lines:

            normalized = line.strip()

            if normalized and normalized == last_line:

                repeat_count += 1

                if repeat_count >= max_repeats:
                    # Stop collecting further repeated lines
                    continue

            else:
                repeat_count = 0

            cleaned_lines.append(line)
            last_line = normalized

        return "\n".join(cleaned_lines).strip()