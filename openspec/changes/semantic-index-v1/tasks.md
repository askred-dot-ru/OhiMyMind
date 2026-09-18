# Tasks: semantic-index-v1

## 1. Schema

- [ ] 1.1 Alembic: tables `knowledge_chunks`, `embed_queue`, `app_settings`; seed `embedding_model=text-embedding-multilingual-e5-small`, `embedding_dim=384`, `embed_generation=0`
- [ ] 1.2 HNSW cosine on `knowledge_chunks.embedding`; unique `(item_id, ordinal)`; do not write retrieval vectors to `knowledge_items.embedding`
- [ ] 1.3 Helper to `ALTER` vector dim + rebuild HNSW when PUT model reports a new dim

## 2. Enqueue from mail

- [ ] 2.1 After `store_mail` / folder park: enqueue eligible folders only (`inbox`, `sent`, `drafts`, `archive`, `user:*`)
- [ ] 2.2 On `spam`/`trash`: delete chunks + queue rows for that item; do not enqueue
- [ ] 2.3 Skip empty subject+body; hash skip when `content_hash` + `model_id` unchanged
- [ ] 2.4 IMAP worker still does not call `LM_STUDIO_URL`

## 3. Embedder

- [ ] 3.1 Package `embedder/` (Compose command `python -m embedder.main`); claim `pending`, batch 128, upsert chunks, `done`/`failed`
- [ ] 3.2 Client: `LM_STUDIO_URL/v1/embeddings`, retries, no e5 prefixes on the default model id, `"ping"` dim probe
- [ ] 3.3 Resume `pending` on start; `EMBEDDING_WORKERS` default 2
- [ ] 3.4 Compose service `embedder` + `.env.example` `LM_STUDIO_URL` (host-shaped)

## 4. API

- [ ] 4.1 `GET /api/v1/search` hybrid/fts/vector, RRF k=60, owner / `as_user_id`, never spam/trash
- [ ] 4.2 Query-embed LRU 256; FTS path unchanged for `/mail/threads?q=`
- [ ] 4.3 `GET /index/status` (per-owner counts); `GET /index/models` admin; `PUT /index/model` admin + confirm-side effect (generation, dim migrate, requeue); `POST /index/retry-failed` admin
- [ ] 4.4 `GET /health` still Postgres-only; LM down ≠ 503

## 5. React

- [ ] 5.1 Non-inbox omnibar → hybrid hits; click opens thread. Inbox: chrome omnibar above buckets; bucket search stays local
- [ ] 5.2 Settings card «Индекс знаний»; nav label «Настройки»; admin select + confirm; user read-only
- [ ] 5.3 Header badge `Индекс N%` + muted omnibar hint while `indexed < eligible`; poll 2s

## 6. Verify

- [ ] 6.1 Eligible letter gets chunks; hybrid search finds it; unique FTS token still finds via `mode=fts` and threads `q`
- [ ] 6.2 Trash/spam: no chunks; restore to Inbox requeues
- [ ] 6.3 Admin model change requeues; user PUT 403; LM down leaves mail UI and `/health` 200

## Context sources

Deltas in this change. `recall` 619. cfsmcp2 numbers in `design.md` D13. No 1C MCP.
