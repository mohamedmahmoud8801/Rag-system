from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import  List
from pathlib import Path
class Settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str
    OPENAI_API_KEY: str

    FILE_ALLOWED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    # MONGODB_URL: str
    # MONGODB_DATABASE: str

    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str 

    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    COHERE_API_KEY: str = None
    HUGGINGFACE_API_KEY: str = None
    HUGGINGFACE_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    HUGGINGFACE_EMBEDDING_SIZE: int = 768
    GENERATION_TIMEOUT: float = 3600.0

    GENERATION_MODEL_ID_LITERAL: List[str] = None
    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None
    INPUT_DEFAULT_MAX_CHARACTERS: int = None
    GENERATION_DEFAULT_MAX_TOKENS: int = None
    GENERATION_DEFAULT_TEMPERATURE: float = None

    VECTOR_DB_BACKEND_LITERAL : List[str] = None
    VECTOR_DB_BACKEND : str
    VECTOR_DB_PATH : str
    VECTOR_DB_DISTANCE_METHOD: str = None
    VECTOR_DB_PGVEC_INDEX_THRESHLOD: int = 100

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

#=======================vlm=======================
    VLM_BACKEND: str = None
    OLLAMA_API_KEY: str = None
    OLLAMA_API_URL: str = None
    VLM_MODEL_ID: str = None
    VLM_DEFAULT_MAX_OUTPUT_TOKENS: int = 20000
    VLM_DEFAULT_TEMPERATURE:float =0.1
    OLLAMA_NUM_CTX: int

# ======================= OCR =======================

    OCR_BACKEND: str = "paddleocr"
    OCR_LANGS:List[str] = ["ar","en"]

# =======================Reranker======================

    RERANKER_PROVIDER:str = "huggingface"
    RERANKER_MODEL_ID:str = "BAAI/bge-reranker-v2-m3"
    RERANK_ENABLED: bool = True
    FINAL_CONTEXTS: int = 5
# ======================= SQL =======================

    SQL_PROVIDER: str = "sqlite"
    SQL_DATABASE_URL: str
    SQL_MAX_ROWS: int = 100
    SQL_MAX_RETRIES: int = 2

# ======================= VIDEO =======================

    VIDEO_PROVIDER: str = "youtube"

    VIDEO_DEFAULT_CHUNK_SIZE: int = 1200
    VIDEO_DEFAULT_CHUNK_OVERLAP: int = 200

    VIDEO_DEFAULT_RETRIEVAL_LIMIT: int = 10
    VIDEO_DEFAULT_GENERATION_MAX_TOKENS: int = 2000
    VIDEO_DEFAULT_GENERATION_TEMPERATURE: float = 0.1



    model_config = SettingsConfigDict(
    env_file=Path(__file__).resolve().parent.parent / ".env",
    env_file_encoding="utf-8",
    extra="ignore"
)
    # class Config:
    #     env_file = ".env"

def get_settings():
    return Settings()