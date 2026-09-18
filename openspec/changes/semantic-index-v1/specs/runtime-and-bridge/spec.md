# Delta for runtime-and-bridge

## MODIFIED Requirements

### Requirement: Env-only configuration

The application MUST read `DATABASE_URL`, `ATTACHMENTS_DIR`, `HTTP_HOST`, `HTTP_PORT`, `PUBLIC_BASE_URL`, `APP_MASTER_KEY`, `SESSION_SECRET`, bootstrap admin vars, optional `GOOGLE_OAUTH_*`, and `LM_STUDIO_URL` from the environment. Optional `EMBEDDING_BATCH_SIZE` (default 128) and `EMBEDDING_WORKERS` (default 2). Source MUST NOT contain Docker Compose DNS names except as example values in `.env.example`. MUST NOT define `ONEC_*` or other 1C connection settings. MUST NOT define DeepSeek / chat-completions keys in this change.

#### Scenario: Host-shaped URLs
- GIVEN `DATABASE_URL=postgresql://ohimymind:ohimymind@127.0.0.1:5432/ohimymind` and `LM_STUDIO_URL=http://127.0.0.1:1234`
- WHEN API, worker, and embedder start outside Compose
- THEN they use those URLs unchanged

### Requirement: Compose development stack

`docker-compose.yml` MUST define services `db` (pgvector/pgvector:pg16), `api`, `worker`, and `embedder`. API MUST serve the React build and `/api/v1`. Worker and embedder MUST NOT bind a public HTTP port. Embedder command MUST be `python -m embedder.main` on the same image. Compose MAY set `LM_STUDIO_URL=http://host.docker.internal:1234` and `extra_hosts` for the host gateway.

#### Scenario: Up
- GIVEN a filled `.env` from `.env.example`
- WHEN `docker compose up --build` succeeds
- THEN GET `/health` returns 200
- AND GET `/` returns the SPA
- AND the `embedder` container is running

### Requirement: Health

`GET /health` MUST return 200 with `{ "status": "ok" }` when Postgres is reachable, without a user session. Database ping failure MUST return 503. Unreachable `LM_STUDIO_URL` MUST NOT by itself make `/health` return 503.

#### Scenario: Health ok while embedder endpoint is down
- GIVEN Postgres is reachable and LM Studio is stopped
- WHEN GET `/health`
- THEN 200 and `status=ok`

## REMOVED Requirements

### Requirement: pgvector without embedding job

## ADDED Requirements

### Requirement: Local embedding job

The system MUST call embeddings only at `LM_STUDIO_URL` + `/v1/embeddings` (OpenAI-compatible). The IMAP worker MUST NOT perform that call. Default `app_settings.embedding_model` MUST be `text-embedding-multilingual-e5-small`. Retrieval writes MUST go to `knowledge_chunks`, not to an external vector database.

#### Scenario: Ingest does not wait on embeddings
- GIVEN LM Studio is stopped
- WHEN the worker stores a new Inbox message
- THEN the `mail_messages` row is committed
- AND `embed_queue.status` is `pending` or `failed` after embedder attempts
- AND IDLE continues

#### Scenario: No cloud embed provider
- GIVEN a running embedder
- WHEN it embeds a passage
- THEN the HTTP request host is the configured `LM_STUDIO_URL`
- AND no GigaChat or OpenAI cloud embedding URL is used

## Context sources

Removed “pgvector without embedding job” (archived runtime spec). Compose today: `db`/`api`/`worker`. LM Studio URL pattern: cfsmcp2 `docker-compose.yml` (ideas only).
