FROM ghcr.io/astral-sh/uv:0.6.14-python3.11-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# ---------- System dependencies ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libjpeg-dev \
    gcc \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    curl \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python dependencies ----------
COPY src/requirements.txt .
RUN uv pip install -r requirements.txt --system

# ---------- Application code ----------
COPY src/ .

# ---------- Alembic ----------
RUN mkdir -p /app/models/db_schemes/ragsystem/
COPY docker/rag/alembic.ini /app/models/db_schemes/ragsystem/alembic.ini

# ---------- Entrypoint ----------
COPY docker/rag/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "3600", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]