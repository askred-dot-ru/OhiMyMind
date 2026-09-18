# Delta for semantic-index

## ADDED Requirements

### Requirement: Embed queue and embedder process

A process distinct from the IMAP worker MUST drain `embed_queue`, call `LM_STUDIO_URL/v1/embeddings`, and upsert `knowledge_chunks`. Queue statuses are `pending`, `done`, `failed`. Embedder start MUST resume `pending` rows. Failed rows keep `error_text` without the message body.

#### Scenario: New eligible mail is queued then chunked
- GIVEN LM Studio reachable and default model loaded
- WHEN a new Inbox message with non-empty `body_text` is stored
- THEN after the embedder drains that row the item has at least one chunk with the current `model_id`
- AND `embed_queue.status` is `done`

### Requirement: Hybrid search API

`GET /api/v1/search` MUST support `mode=hybrid` (default, RRF k=60 of FTS + cosine), `fts`, and `vector`. Default limit 50, max 100. Empty `q` MUST 400. Spam and trash MUST never appear even if orphan chunks exist. Vector cosine MUST use only chunks whose `model_id` equals `app_settings.embedding_model`.

#### Scenario: Unique token via fts mode
- GIVEN a stored body containing a unique token
- WHEN GET `/api/v1/search?q=<token>&mode=fts`
- THEN that item is in hits for the owner

#### Scenario: Hybrid default
- GIVEN the same stored item
- WHEN GET `/api/v1/search?q=<token>` with no mode
- THEN the item is in hits
- AND `mode` is treated as hybrid

### Requirement: Active embedding model

The installation has exactly one active `model_id` in `app_settings`. Default is `text-embedding-multilingual-e5-small`. Changing it MUST probe `/v1/embeddings`, persist `embedding_dim`, migrate the vector column if dim changed, increment `embed_generation`, and enqueue every eligible item. Vector search MUST ignore chunks with a previous `model_id`.

#### Scenario: Admin changes model
- GIVEN admin and a reachable embed endpoint that serves a different embedding model id
- WHEN admin PUT `/api/v1/index/model` with that id after UI confirm
- THEN `embedding_model` is the new id
- AND eligible items have `pending` (or in-flight) queue rows
- AND search cosine does not use the previous `model_id`

#### Scenario: Probe failure does not switch
- GIVEN LM Studio is stopped
- WHEN admin PUT `/api/v1/index/model`
- THEN the response is an error (5xx)
- AND `embed_generation` is unchanged

### Requirement: Index status UI

`/settings` MUST show a card **Индекс знаний** using existing `.card` styles. It MUST show endpoint ping, current model, dim, generation, state `ready` | `indexing` | `endpoint_down` | `error`, a progress bar `indexed/eligible` for the viewer, failed count, and last error without bodies. Admin MAY select a model from `GET /index/models` (plus a free-id field) and apply with `window.confirm`. `LM_STUDIO_URL` is displayed, not edited. The mail header MUST show badge `Индекс N%` while `indexed < eligible` or state is not `ready`. The settings nav label MUST be **Настройки**.

#### Scenario: Progress while indexing
- GIVEN the current user has 10 eligible letters and 4 already chunked with the current model
- WHEN they open Settings
- THEN the card shows 4 / 10 (or equivalent percent)
- AND the mail header badge is visible

#### Scenario: Apply requires confirm
- GIVEN admin selected a different model id than the current setting
- WHEN they click apply and dismiss confirm
- THEN PUT is not sent
- AND the stored model is unchanged

## Context sources

Settings `.card`: `web/src/pages/Settings.tsx`. Chunk budgets: cfsmcp2 `bsl_embed.py` 512 preset. RRF/chat-later: cfsmcp2 ARCHITECTURE §10.
