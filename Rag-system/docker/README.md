```markdown
# MiniRAG — Docker Setup

MiniRAG is a Retrieval-Augmented Generation (RAG) system built with FastAPI, PostgreSQL/PGVector, Qdrant, Ollama, and a React frontend.

This repository provides a Docker-based development environment with monitoring and observability tools.

---

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Frontend Build](#frontend-build)
- [Environment Configuration](#environment-configuration)
- [Start the Application](#start-the-application)
- [Services](#services)
- [Access URLs](#access-urls)
- [Database Configuration](#database-configuration)
- [Alembic Migrations](#alembic-migrations)
- [Vector Database Configuration](#vector-database-configuration)
- [Ollama Models](#ollama-models)
- [Monitoring](#monitoring)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [Volumes and Data Management](#volumes-and-data-management)

---

## Architecture

The Docker environment includes the following services:

| Service | Description |
|---|---|
| FastAPI | Backend API and application logic |
| Nginx | Reverse proxy |
| PostgreSQL + PGVector | Relational database and vector storage |
| Qdrant | Alternative vector database |
| Ollama | Local LLM and VLM inference |
| Ollama Pull | Downloads required Ollama models |
| Prometheus | Metrics collection |
| Grafana | Metrics visualization |
| PostgreSQL Exporter | PostgreSQL metrics |
| Node Exporter | Host metrics |

The React frontend is built separately and served by FastAPI from `/app/static`. It does not require a separate frontend container.

---

## Prerequisites

Make sure the following tools are installed:

- Docker Engine
- Docker Compose
- Python
- Node.js and npm
- Git

Verify Docker:

```bash
docker --version
docker compose version
```

Verify Node.js:

```bash
node --version
npm --version
```

---

## Project Structure

The main project structure includes:

```text
Rag-system/
├── docker/
│   ├── compose.yaml
│   ├── env/
│   │   ├── .env.example.app
│   │   ├── .env.example.postgres
│   │   ├── .env.example.grafana
│   │   └── .env.example.postgres-exporter
│   └── ...
├── frontend/
│   ├── package.json
│   └── ...
├── src/
│   ├── main.py
│   ├── models/
│   │   └── db_schemes/
│   │       └── ragsystem/
│   │           ├── alembic/
│   │           ├── alembic.ini
│   │           └── alembic.ini.example
│   └── ...
└── README.md
```

The structure above is illustrative. Refer to the actual repository tree for the complete list of files.

---

## Frontend Build

Build the React frontend before building the Docker application image.

From the project root:

```bash
cd frontend

npm install
npm run build

cd ..
```

Make sure the frontend build output is available to the backend Docker image.

The frontend is served by FastAPI from:

```text
/app/static
```

If the frontend is missing, verify that the Docker build copies the generated frontend files to the expected location.

---

## Environment Configuration

Environment templates are located in:

```text
docker/env/
```

Navigate to the directory:

```bash
cd docker/env
```

Create the environment files:

```bash
cp .env.example.app .env.app
cp .env.example.postgres .env.postgres
cp .env.example.grafana .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter
```

Return to the project root:

```bash
cd ../..
```

> If your Compose configuration references environment files using different paths, adjust these commands to match the actual repository structure.

### Application Environment

Edit:

```text
docker/env/.env.app
```

Configure the application settings.

#### PostgreSQL

Inside Docker Compose, use the PostgreSQL service name as the hostname:

```env
POSTGRES_HOST=pgvector
```

Do not use `localhost` to connect to another Docker container.

#### Ollama

When the Ollama service is named `ollama` in Docker Compose:

```env
OPENAI_API_URL=http://ollama:11434/v1/
OLLAMA_API_URL=http://ollama:11434/v1/
```

These URLs are for communication between containers within the same Docker Compose network.

#### Vector Database

Select the vector database backend:

```env
VECTOR_DB_BACKEND=PGVECTOR
```

Or:

```env
VECTOR_DB_BACKEND=QDRANT
```

Make sure the application configuration supports the selected backend.

#### JWT Secret

Generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the generated value into the appropriate environment variable in `.env.app`.

#### Authentication

Configure the authorized administrator identifiers:

```env
AUTH_ADMIN_IDENTIFIERS=
```

Add the required identifiers according to your authentication implementation.

#### Langfuse

If Langfuse integration is enabled, configure the required keys and base URL in `.env.app`.

Do not commit real API keys, passwords, or secrets to Git.

---

## Start the Application

From the project root:

```bash
cd docker

docker compose up --build -d
```

Check the running containers:

```bash
docker compose ps
```

Follow the logs:

```bash
docker compose logs -f
```

### Check Ollama Model Download

The `ollama-pull` service downloads the configured models.

Check its logs:

```bash
docker compose logs -f ollama-pull
```

Wait until the required models have been downloaded and the service reports that the models are ready.

Model downloads may take time depending on your internet connection and available disk space.

### Start Specific Services

To start selected services:

```bash
docker compose up -d fastapi nginx pgvector qdrant ollama
```

This command starts the specified services and their required dependencies.

---

## Services

### FastAPI

The backend API runs using Gunicorn with Uvicorn workers in the Docker environment.

The number of workers is configurable through the Docker service configuration.

### Nginx

Nginx acts as a reverse proxy and forwards incoming requests to the backend.

### PostgreSQL + PGVector

PostgreSQL provides relational storage and vector search capabilities through PGVector.

### Qdrant

Qdrant provides an alternative vector database backend.

### Ollama

Ollama provides local LLM and VLM inference.

Configured models include:

- `qwen2.5:7b-instruct`
- `qwen2.5vl:3b`

The actual models used depend on the model configuration and environment variables.

---

## Access URLs

After starting the Docker environment, the following services may be available:

| Service | URL |
|---|---|
| FastAPI | http://localhost:8000 |
| FastAPI Swagger UI | http://localhost:8000/docs |
| FastAPI OpenAPI | http://localhost:8000/openapi.json |
| Nginx | http://localhost |
| Ollama API | http://localhost:11434 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| Qdrant API | http://localhost:6333 |
| Qdrant Dashboard | http://localhost:6333/dashboard |

These ports assume the Compose file publishes the corresponding container ports to the host.

---

## Database Configuration

### PostgreSQL

The PostgreSQL database is configured through:

```text
docker/env/.env.postgres
```

Make sure the application and PostgreSQL service use matching database credentials and database names.

The application connects to PostgreSQL using the Docker service name:

```text
pgvector
```

### Database Backup

Create a PostgreSQL backup:

```bash
docker compose exec pgvector \
  pg_dump -U <username> -d ragsystem > ragsystem_backup.sql
```

Replace `<username>` with the configured PostgreSQL username.

### Database Restore

Restore a backup:

```bash
docker compose exec -T pgvector \
  psql -U <username> -d ragsystem < ragsystem_backup.sql
```

Make sure the target database exists before restoring.

---

## Alembic Migrations

The Alembic configuration is located inside the RAG system database scheme directory:

```text
src/models/db_schemes/ragsystem/
```

The directory contains:

```text
alembic/
alembic.ini
alembic.ini.example
```

Do not copy Alembic configuration from an unrelated Docker directory.

Run migrations using the configuration and working directory expected by your project's migration setup.

For example, if the Alembic configuration is designed to run from the `ragsystem` directory:

```bash
cd src/models/db_schemes/ragsystem
```

Check the configuration:

```bash
cat alembic.ini
```

Then run:

```bash
alembic upgrade head
```

> Make sure the database connection settings and Python import paths are correctly configured before running migrations. The exact migration command depends on how Alembic is configured in the project.

---

## Vector Database Configuration

MiniRAG supports PGVector and Qdrant, depending on the application's configuration.

### Select PGVector

Update `.env.app`:

```env
VECTOR_DB_BACKEND=PGVECTOR
```

### Select Qdrant

Update `.env.app`:

```env
VECTOR_DB_BACKEND=QDRANT
```

Restart the application after changing the backend:

```bash
docker compose restart fastapi
```

### Reindex Documents

After switching vector database backends, reindex your documents if required.

Example:

```bash
curl -X POST \
  http://localhost:8000/api/v1/nlp/index/push/1 \
  -H "Content-Type: application/json" \
  -d '{"do_reset": 1}'
```

Verify the request body and endpoint parameters against the current API implementation before running a reset or reindex operation.

---

## Ollama Models

The Docker environment uses Ollama for local model inference.

Configured models:

| Model | Purpose |
|---|---|
| `qwen2.5:7b-instruct` | Text generation |
| `qwen2.5vl:3b` | Vision-language tasks |

### Check Ollama

```bash
docker compose ps ollama
```

Check logs:

```bash
docker compose logs -f ollama
```

Check available models:

```bash
docker compose exec ollama ollama list
```

### Pull a Model Manually

```bash
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

For the vision-language model:

```bash
docker compose exec ollama ollama pull qwen2.5vl:3b
```

### Test Ollama API

```bash
curl http://localhost:11434/api/tags
```

If the API is unavailable, verify that the Ollama container is running and that port `11434` is published.

---

## Monitoring

The Docker environment includes Prometheus and Grafana for monitoring application and infrastructure metrics.

### Prometheus

Prometheus collects metrics from configured targets.

Access:

```text
http://localhost:9090
```

### Grafana

Access:

```text
http://localhost:3000
```

Use the credentials configured in the Grafana environment file.

Do not assume the default Grafana credentials if they have been changed.

### FastAPI Metrics

The application exposes metrics through:

```text
/metrics
```

Metrics may include:

- Request counts
- Request latency
- HTTP status codes
- Application-level metrics

Metrics configuration is implemented through the project's metrics setup module.

### Prometheus Exporters

The environment includes:

- PostgreSQL Exporter
- Node Exporter

These exporters provide database and system-level metrics.

### Grafana Dashboards

Useful dashboard references:

- [FastAPI Observability](https://grafana.com/grafana/dashboards/18739-fastapi-observability/)
- [Node Exporter Full](https://grafana.com/grafana/dashboards/1860-node-exporter-full/)
- [Qdrant Dashboard](https://grafana.com/grafana/dashboards/23033-qdrant/)
- [PostgreSQL Exporter](https://grafana.com/grafana/dashboards/12485-postgresql-exporter/)

Configure Prometheus as a Grafana data source using the internal Docker service URL:

```text
http://prometheus:9090
```

---

## Development Workflow

### Run FastAPI Locally

For local development, activate the appropriate Python environment and navigate to the source directory:

```bash
cd src
```

Run the backend:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> This is a local development command. The Docker environment may use a different port or Gunicorn configuration.

### Run Docker in Development

Start the Docker environment:

```bash
cd docker
docker compose up --build -d
```

Follow backend logs:

```bash
docker compose logs -f fastapi
```

Restart the backend:

```bash
docker compose restart fastapi
```

Rebuild the backend image:

```bash
docker compose up -d --build fastapi
```

If frontend files are included in the backend image, rebuild the frontend before rebuilding the backend.

---

## Gunicorn Workers and Memory

The Docker backend uses Gunicorn with Uvicorn workers.

The number of workers should be selected according to:

- Available RAM
- CPU cores
- Model loading behavior
- Request concurrency
- Whether models are loaded separately in each worker

LLM and VLM models can consume substantial memory.

Increasing the worker count does not automatically improve performance and may cause memory exhaustion.

For local development, consider using fewer workers if memory usage is high.

Monitor container resource usage:

```bash
docker stats
```

If your Compose service has a different container name, use the actual name shown by:

```bash
docker compose ps
```

Adjust the Gunicorn command through the project's Docker service configuration.

---

## Troubleshooting

### FastAPI Cannot Connect to PostgreSQL

Check PostgreSQL:

```bash
docker compose ps pgvector
```

Check logs:

```bash
docker compose logs pgvector
```

Verify:

- PostgreSQL credentials
- Database name
- Docker service hostname
- Database readiness
- Environment variables

Inside Docker, use the PostgreSQL service name rather than `localhost`.

### Ollama Model Is Not Available

Check Ollama:

```bash
docker compose logs ollama
```

Check model download logs:

```bash
docker compose logs ollama-pull
```

List downloaded models:

```bash
docker compose exec ollama ollama list
```

Pull missing models manually if necessary.

### Nginx Returns 502 or Connection Refused

Check the backend:

```bash
docker compose ps fastapi
docker compose logs fastapi
```

Check Nginx:

```bash
docker compose logs nginx
```

Verify that Nginx uses the correct FastAPI service hostname and port.

### Frontend Is Missing

Verify that:

1. The frontend dependencies are installed.
2. The frontend build completed successfully.
3. The generated frontend files exist.
4. The Docker image copies the build output to `/app/static`.

Build the frontend again:

```bash
cd frontend
npm install
npm run build
cd ..
```

Then rebuild the relevant Docker image.

### Container Is Not Starting

Check:

```bash
docker compose ps
docker compose logs <service_name>
```

Restart the affected service:

```bash
docker compose restart <service_name>
```

If the image or build configuration changed:

```bash
docker compose up -d --build <service_name>
```

---

## Volumes and Data Management

Docker volumes preserve application data between container restarts.

Important data may include:

- PostgreSQL database files
- Ollama model files
- Application data

List volumes:

```bash
docker volume ls
```

Inspect a volume:

```bash
docker volume inspect <volume_name>
```

List containers:

```bash
docker compose ps
```

### Stop Containers

```bash
docker compose down
```

This stops and removes containers and the Compose network while preserving named volumes.

### Remove Containers and Volumes

```bash
docker compose down -v --remove-orphans
```

**Warning:** This command removes Compose-managed volumes and may permanently delete PostgreSQL data, Ollama models, and other persistent application data.

Back up important data before running it.

Avoid removing all Docker volumes globally unless you intentionally want to delete data belonging to other projects.

---

## License

Add the project's license information here.
```
