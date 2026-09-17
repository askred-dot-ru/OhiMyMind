# Delta for knowledge-streams

## ADDED Requirements

### Requirement: Knowledge item envelope

The system SHALL persist every ingested object as a `knowledge_items` row with `stream_kind` in `mail`, `messenger`, `llm_session`; `owner_user_id`; created/updated timestamps; and nullable `embedding` of type `vector(1536)`. v1 application code MUST insert only `stream_kind=mail`.

#### Scenario: Mail ingest creates an envelope
- GIVEN a connected mail account owned by user U
- WHEN the worker stores a new IMAP message
- THEN a `knowledge_items` row exists with `stream_kind=mail` and `owner_user_id=U`
- AND `embedding` IS NULL

#### Scenario: Reserved kinds are not writable in v1
- GIVEN the v1 API or worker
- WHEN a client attempts to create `stream_kind=messenger` or `llm_session`
- THEN the write is rejected (HTTP 400 or worker skip with log)
- AND no `knowledge_items` row is inserted

### Requirement: Per-kind native structure

Mail-specific fields MUST live in `mail_*` tables keyed to `knowledge_items.id`. The system MUST NOT model messenger chats or LLM sessions as IMAP folders.

#### Scenario: Mail payload is not a generic folder-only row
- GIVEN a stored mail item
- WHEN the API loads a thread
- THEN IMAP UID, folder map, Message-ID, and flags come from `mail_*` tables
- AND not from a generic folder table reused for other kinds

### Requirement: Topics table without v1 UI

The schema MUST include `topics` and `item_topics`. v1 UI and API MUST NOT expose create/list/assign topic endpoints.

#### Scenario: Topics exist but are unused
- GIVEN a migrated database
- WHEN a v1 client lists HTTP routes
- THEN no `/topics` resource exists
- AND tables `topics` and `item_topics` exist empty

### Requirement: Distribution routes stub

The schema MUST include `distribution_routes`. v1 MUST NOT dequeue or deliver routes.

#### Scenario: No dispatcher
- GIVEN a mail item
- WHEN ingest completes
- THEN no `distribution_routes` row is required
- AND no background job delivers the item to another system
