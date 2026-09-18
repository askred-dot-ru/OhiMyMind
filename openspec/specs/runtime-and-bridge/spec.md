# runtime-and-bridge Specification

## Purpose
Env-only runtime (Compose `db`/`api`/`worker`), pgvector column without an embedding job, health check, and no 1C tables/routes/env in v1.

## Requirements

### Requirement: Env-only configuration

The application MUST read `DATABASE_URL`, `ATTACHMENTS_DIR`, `HTTP_HOST`, `HTTP_PORT`, `PUBLIC_BASE_URL`, `APP_MASTER_KEY`, `SESSION_SECRET`, bootstrap admin vars, and optional `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` from the environment. Source MUST NOT contain Docker Compose DNS names except as example values in `.env.example`. v1 MUST NOT define `ONEC_*` or other 1C connection settings.

#### Scenario: Host-shaped URLs
- GIVEN `DATABASE_URL=postgresql://ohimymind:ohimymind@127.0.0.1:5432/ohimymind`
- WHEN API and worker start outside Compose
- THEN they use that URL unchanged

### Requirement: Compose development stack

`docker-compose.yml` MUST define services `db` (pgvector/pgvector:pg16), `api`, and `worker`. API MUST serve the React build and `/api/v1`. Worker MUST NOT bind a public HTTP port.

#### Scenario: Up
- GIVEN a filled `.env` from `.env.example`
- WHEN `docker compose up --build` succeeds
- THEN GET `/health` returns 200
- AND GET `/` returns the SPA

### Requirement: pgvector without embedding job

Migrations MUST `CREATE EXTENSION IF NOT EXISTS vector` and add `knowledge_items.embedding vector(1536)`. v1 MUST NOT call an embedding HTTP API.

#### Scenario: No outbound embed
- GIVEN a synced message
- WHEN ingest finishes
- THEN `embedding` is NULL

### Requirement: No 1C in v1

v1 MUST NOT open TCP/HTTP to 1C, MUST NOT expose `/onec` (or equivalent) routes, and MUST NOT store 1C logins. A later change MAY add outbound HTTP to an external base URL; that change is out of this spec.

#### Scenario: No 1C routes
- GIVEN a running API
- WHEN a client requests `/api/v1/onec/execute`
- THEN the response is HTTP 404 (route absent)

### Requirement: Health

`GET /health` MUST return 200 with `{ "status": "ok" }` when Postgres is reachable, without a user session. Database ping failure MUST return 503.

#### Scenario: Health ok
- GIVEN Postgres is reachable
- WHEN GET `/health`
- THEN 200 and `status=ok`
