# Proposal: semantic-index-v1

## Why

Mail-stream v1 stored a full local copy and FTS (`simple` on subject+body) and left `knowledge_items.embedding` NULL. The product is a **knowledge-stream** store, not a mail client. The next increment is a local embedding index plus hybrid search in the existing mail UI. Chat with an LLM (DeepSeek / OpenAI-compatible completions) is a later change.

## What changes

1. **Chunks + queue:** `knowledge_chunks` hold retrieval vectors. IMAP ingest enqueues; it does not call an embed HTTP API. Spam and trash are never indexed; leaving those folders deletes chunks.
2. **Embedder process:** Compose service `embedder` calls a **local** OpenAI-compatible `/v1/embeddings` (`LM_STUDIO_URL`, same pattern as cfsmcp2). Default model `text-embedding-multilingual-e5-small`. Admin can change `model_id` in Settings; that reindexes the whole eligible corpus.
3. **Hybrid search:** `GET /api/v1/search` (RRF of FTS + cosine). Mail omnibar uses it. Folder-list FTS `q` and inbox bucket filters stay.
4. **UI:** Settings card «Индекс знаний» (progress + admin model dialog). Header badge while the current user's eligible items are not fully indexed.

## Scope

| In scope | Out of scope |
|---|---|
| `knowledge_chunks`, `embed_queue`, `app_settings` (model/dim/generation) | LLM chat UI, tool-calling, DeepSeek completions, `llm_session` ingest |
| Local `/v1/embeddings` (LM Studio). No GigaChat/OpenAI cloud embed | Second vector DB (zvec, Qdrant). Do not vendor cfsmcp2 (AGPL) |
| Hybrid API + mail omnibar + settings card + header badge | Auto-topics, attachment/OCR index, summary vector on `knowledge_items` |
| Index `inbox`, `sent`, `drafts`, `archive`, `user:*` | Index `spam`, `trash` |
| pgvector HNSW on chunks; migrate dim when the model dim changes | ChatOps from messengers; 1C |

## Approach

| # | Direction |
|---|---|
| 1 | Alembic: chunks, queue, app_settings; HNSW; default model + dim 384 |
| 2 | `embedder` service; enqueue from `store_mail`; skip/delete spam/trash |
| 3 | Hybrid `/api/v1/search` + index status/models/retry (ACL) |
| 4 | React: omnibar → search hits; Settings card; header badge |
| 5 | Compose: `embedder` + `LM_STUDIO_URL` via env (`host.docker.internal` in Compose) |

## Success criteria

- After ingest of an Inbox (or other eligible) letter, a chunk with `model_id` = current setting appears without blocking IDLE.
- `GET /api/v1/search?q=` hybrid returns that thread to the owner; a unique FTS token still hits; spam/trash never appear.
- Moving a message to Trash removes its chunks; restoring to Inbox requeues.
- Admin confirm in Settings changes the model → `embed_generation` increments → eligible corpus requeues; vector search uses only the new `model_id`.
- User role cannot PUT the model (403). IMAP and `/health` stay up if LM Studio is down (`index` state `endpoint_down`).
- No chat routes; no DeepSeek env; no call to an embedding provider other than `LM_STUDIO_URL`.
- No zvec / sqlite-vec; no copied cfsmcp2 modules.

## Risks

- LM Studio not running → index stalls; mail must keep working.
- Model dim change requires `ALTER` of `knowledge_chunks.embedding` + rebuild HNSW before new writes.
- Full reindex of a large mailbox is slow on CPU; UI must show counts, not a frozen bar.
- e5-small via LM Studio: do **not** add `query:`/`passage:` prefixes (cfsmcp2 default for this model id). Instruct-e5 models are a future model pick, not this default.

## Context sources

Verified: `openspec/specs/{knowledge-streams,runtime-and-bridge,mail-stream,identity-acl}`; code `app/models.py` (`Vector(1536)` unused), `store_mail.py` (sets `embedding=None`), `mail.py` FTS `plainto_tsquery`; UI omnibar «Поиск знаний, писем, тегов». User locks 2026-09-18. cfsmcp2 0.2.35 ARCHITECTURE / `bsl_embed.py` chunk budgets (ideas only, AGPL). `recall` 585–586, 618–619. 1C MCP skipped (not a 1C change). `templatesearch` skipped (no 1C template).
