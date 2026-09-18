# Delta for knowledge-streams

## MODIFIED Requirements

### Requirement: Knowledge item envelope

The system SHALL persist every ingested object as a `knowledge_items` row with `stream_kind` in `mail`, `messenger`, `llm_session`; `owner_user_id`; created/updated timestamps. Column `knowledge_items.embedding` MAY remain nullable and MUST NOT be used for retrieval in this change. Application code MUST insert only `stream_kind=mail`. Retrieval vectors MUST live on `knowledge_chunks` for the current `app_settings.embedding_model`.

#### Scenario: Mail ingest creates an envelope
- GIVEN a connected mail account owned by user U
- WHEN the worker stores a new IMAP message in an eligible folder
- THEN a `knowledge_items` row exists with `stream_kind=mail` and `owner_user_id=U`
- AND an `embed_queue` row is `pending` for that item (or skipped if subject and `body_text` are both empty)

#### Scenario: Envelope vector is not the search index
- GIVEN a stored mail item
- WHEN hybrid search runs
- THEN cosine uses `knowledge_chunks.embedding` where `model_id` equals the current setting
- AND `knowledge_items.embedding` is not required to be non-NULL

#### Scenario: Reserved kinds are not writable
- GIVEN the API or worker
- WHEN a client attempts to create `stream_kind=messenger` or `llm_session`
- THEN the write is rejected (HTTP 400 or worker skip with log)
- AND no `knowledge_items` row is inserted

## ADDED Requirements

### Requirement: Knowledge chunks

The system SHALL store zero or more `knowledge_chunks` rows per `knowledge_items.id`: `ordinal`, passage `body`, `content_hash`, `embedding`, `model_id`. Unique `(item_id, ordinal)`. Passage text is `subject | from_addr | sent_at ISO | body_text` split with passage_max_chars=1350, chunk_size=1100, overlap=130, max_chunks=12. HTML and attachments MUST NOT be embedded.

#### Scenario: Long body becomes several chunks
- GIVEN an eligible message whose `body_text` is longer than the chunk window
- WHEN the embedder finishes that item
- THEN at least two `knowledge_chunks` rows exist for the item
- AND each has `model_id` equal to the current setting

### Requirement: Eligible folders only

The embedder MUST index mail in canonical folders `inbox`, `sent`, `drafts`, `archive`, and `user:*`. It MUST NOT index `spam` or `trash`.

#### Scenario: Trash is not indexed
- GIVEN a message parked in `trash`
- WHEN the embedder drains the queue
- THEN that item has zero `knowledge_chunks`
- AND no `pending` queue row remains for it

#### Scenario: Move to trash drops the index
- GIVEN an Inbox message with chunks
- WHEN the user deletes it (canonical trash)
- THEN its `knowledge_chunks` rows are deleted
- AND hybrid search no longer returns it

#### Scenario: Restore requeues
- GIVEN a trashed message moved back to `inbox`
- WHEN store/park completes
- THEN an `embed_queue` row is `pending` for that item

## Context sources

Envelope/chunks vs `knowledge_items.embedding` unused: `app/models.py`, archived knowledge-streams spec. Folders: `app/providers.py`. User: no spam/trash.
