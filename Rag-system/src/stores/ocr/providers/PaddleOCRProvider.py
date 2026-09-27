import base64
import io

import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from helpers.config import Settings
from ..OCRInterface import OCRInterface


class PaddleOCRProvider(OCRInterface):

    def __init__(self, config: Settings):
        self.config = config

        # Lazy-loaded OCR engines per language
        self._ocr_engines = {}

        # Languages to try for mixed Arabic/English documents
        self.ocr_languages = config.OCR_LANGS

    def _get_ocr_engine(self, lang: str):

        if lang not in self._ocr_engines:

            self._ocr_engines[lang] = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
                use_textline_orientation=True,
                device = "cpu"
            )

        return self._ocr_engines[lang]

    def _run_single_lang(self, image_array, lang: str):

        ocr_engine = self._get_ocr_engine(lang)
        result = ocr_engine.predict(image_array)

        texts = []
        scores = []

        for res in result:

            if not isinstance(res, dict):
                continue

            rec_texts = res.get("rec_texts", [])
            rec_scores = res.get("rec_scores", [])

            texts.extend(rec_texts)
            scores.extend(rec_scores)

        avg_score = (
            sum(scores) / len(scores)
            if scores else 0.0
        )

        return {
            "text": "\n".join(texts),
            "texts": texts,
            "scores": scores,
            "avg_score": avg_score,
            "lang": lang,
        }

    def extract_text(
        self,
        image_base64: str,
        image_type: str = "image/png"
    ):

        try:
            image_bytes = base64.b64decode(image_base64)

            image = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")

            image_array = np.array(image)

            best_result = None

            for lang in self.ocr_languages:

                result = self._run_single_lang(
                    image_array=image_array,
                    lang=lang
                )

                if (
                    best_result is None
                    or result["avg_score"] > best_result["avg_score"]
                ):
                    best_result = result

            return {
                "text": best_result["text"],
                "texts": best_result["texts"],
                "scores": best_result["scores"],
                "detected_lang": best_result["lang"],
            }

        except Exception as e:
            raise RuntimeError(
                f"PaddleOCR extraction failed: {str(e)}"
            ) from e