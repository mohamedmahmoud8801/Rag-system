# ============================================================
# App
# ============================================================
APP_NAME=mini-RAG
APP_VERSION=0.1

FILE_ALLOWED_TYPES=["text/plain","application/pdf","image/jpeg","image/png","image/webp","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]
FILE_MAX_SIZE=10
FILE_DEFAULT_CHUNK_SIZE=512000

# ============================================================
# PostgreSQL
# ============================================================
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=pgvector
POSTGRES_PORT=5432
POSTGRES_MAIN_DATABASE=ragsystem

# ============================================================
# SQL (Excel store + connected databases)
# ============================================================
SQL_PROVIDER=sqlite
SQL_DATABASE_URL=sqlite:///assets/database/sql/ecommerce.db
SQL_MAX_ROWS=100
SQL_MAX_RETRIES=2
SQL_ALLOW_CLIENT_DATABASE_URL=false
SQL_SEMANTIC_VERIFY=false
SQL_SCHEMA_CACHE_TTL=300

EXCEL_MAX_ROWS_PER_SHEET=100000
EXCEL_SQL_DIR=assets/database/excel

CONNECTIONS_DB_PATH=assets/database/connections.db
CONNECTIONS_SECRET_KEY=
CONNECTIONS_ALLOW_PRIVATE_HOSTS=true
CONNECTIONS_MAX_PER_PROJECT=10
SQLITE_CONNECT_DIR=assets/database/sql
SQLITE_UPLOAD_MAX_MB=50

# ============================================================
# LLM
# ============================================================
GENERATION_BACKEND=OPENAI
EMBEDDING_BACKEND=HUGGINGFACE

OPENAI_API_KEY=ollama
OPENAI_API_URL=http://ollama:11434/v1/
COHERE_API_KEY=
HUGGINGFACE_API_KEY=

GENERATION_MODEL_ID_LITERAL=["gpt-3.5-turbo","gpt-4","qwen2.5-coder:7b","qwen2.5:7b-instruct"]
GENERATION_MODEL_ID=qwen2.5:7b-instruct
EMBEDDING_MODEL_ID=intfloat/multilingual-e5-base
EMBEDDING_MODEL_SIZE=768

INPUT_DEFAULT_MAX_CHARACTERS=4000
GENERATION_DEFAULT_MAX_TOKENS=200
GENERATION_DEFAULT_TEMPERATURE=0.1

# ============================================================
# VLM (Ollama)
# ============================================================
VLM_BACKEND=OLLAMA
OLLAMA_API_KEY=ollama
OLLAMA_API_URL=http://ollama:11434/v1/
OLLAMA_NUM_CTX=2048
VLM_MODEL_ID=qwen2.5vl:3b
VLM_DEFAULT_MAX_OUTPUT_TOKENS=256
VLM_DEFAULT_TEMPERATURE=0

# ============================================================
# OCR
# ============================================================
OCR_BACKEND=PADDLEOCR
OCR_LANGS=["ar","en"]

# ============================================================
# Vector DB
# ============================================================
VECTOR_DB_BACKEND_LITERAL=["QDRANT","PGVECTOR"]
VECTOR_DB_BACKEND=PGVECTOR
VECTOR_DB_PATH=qdrant_db
VECTOR_DB_DISTANCE_METHOD=cosine
VECTOR_DB_PGVEC_INDEX_THRESHLOD=300

# ============================================================
# Video
# ============================================================
VIDEO_PROVIDER=youtube
VIDEO_DEFAULT_CHUNK_SIZE=1200
VIDEO_DEFAULT_CHUNK_OVERLAP=200
VIDEO_DEFAULT_RETRIEVAL_LIMIT=10
VIDEO_DEFAULT_GENERATION_MAX_TOKENS=2000
VIDEO_DEFAULT_GENERATION_TEMPERATURE=0.1

# ============================================================
# i18n
# ============================================================
PRIMARY_LANG=en
DEFAULT_LANG=en

# ============================================================
# Reranker
# ============================================================
RERANKER_PROVIDER=huggingface
RERANKER_MODEL_ID=BAAI/bge-reranker-v2-m3
RERANK_ENABLED=true
FINAL_CONTEXTS=5
NEIGHBOR_WINDOW=2
NEIGHBOR_MIN_RERANK=0.5

# ============================================================
# Auth
# ============================================================
AUTH_ENABLED=true
AUTH_DATABASE_URL=sqlite:///assets/database/auth.db
JWT_SECRET_KEY=CHANGE_ME_TO_A_REAL_SECRET_AT_LEAST_32_CHARS
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=14
AUTH_ADMIN_IDENTIFIERS=you@gmail.com
AUTH_DEFAULT_REGION=EG

# OTP settings
AUTH_OTP_LENGTH=6
AUTH_OTP_MINUTES=10
AUTH_OTP_MAX_ATTEMPTS=5
AUTH_OTP_RESEND_SECONDS=60
AUTH_OTP_MAX_PER_HOUR=5

# Password / lockout
AUTH_PASSWORD_MIN_LENGTH=8
AUTH_MAX_FAILED_LOGINS=5
AUTH_LOCK_MINUTES=15
AUTH_RATE_LIMIT_PER_MINUTE=30

# ============================================================
# Email / SMS delivery
# ============================================================
AUTH_EMAIL_DELIVERY=console
AUTH_SMS_DELIVERY=console

# SMTP (used only when AUTH_EMAIL_DELIVERY=smtp)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_STARTTLS=true


===========llm inference and serving===============
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL="https://cloud.langfuse.com"