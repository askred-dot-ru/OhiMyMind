# Memory — Oh!MyMind

Working project memory for AI agents. Eligibility vs `1c-templates-mcp` (`remember` / `recall`) — portfolio `AGENTS.md → Project memory`.

Narrative in English; keep product and stream names as-is.

## 2026-09-17 — Product name

- **Scope:** branding.
- **Rule:** Human product name is **Oh!MyMind**. Where `!` is illegal (DNS, some identifiers) write **OhiMyMind**. GitHub **https://github.com/askred-dot-ru/OhiMyMind**. Local path `z/ohimymind/`. Do not spell the product as MyMind / MyMinde in UI or docs.
- **Source:** user, 2026-09-17.

## 2026-09-17 — Product: knowledge streams, not a mail client

- **Scope:** Oh!MyMind (`z/ohimymind/`). Do **not** implement this product inside 1C extension `Почта` (`z0/z0_C/`).
- **Rule:** Oh!MyMind is a system for **classification, storage, and distribution of knowledge streams**. Mail is only stream #1 — the first and simplest stream, not the whole product. Do not design or name the system as a mail client.
- **Why:** v1 mail UI is an ingest surface; later streams (messengers, LLM sessions) must fit the same envelope.
- **Source:** user, 2026-09-17.

## 2026-09-17 — Each stream has its own structure

- **Scope:** data model.
- **Rule:** Common envelope (owner, timestamps, ACL, embeddings, distribution routes) plus **per-kind** tables. Native structures:
  - **mail (v1):** IMAP folders, labels, threads (`Message-ID` / `In-Reply-To` / `References`), flags.
  - **messenger (not v1):** Telegram / WhatsApp / Teams chats and threads.
  - **llm_session (not v1):** LLM conversation sessions and session **artifacts**.
- **Why:** do not force Gmail-style folders onto chats or LLM sessions.
- **Source:** user, 2026-09-17.

## 2026-09-17 — Messengers are sources, not agent control

- **Scope:** future messenger ingest; agent behaviour.
- **Rule:** Messengers are **information sources** to collect, store, and index (FTS + later vectors). They are **not** a control channel for the agent (no ChatOps, no “command the assistant from Telegram/WhatsApp/Teams”).
- **Source:** user, 2026-09-17.

## 2026-09-17 — GitHub

- **Scope:** hosting.
- **Rule:** Canonical remote is **https://github.com/askred-dot-ru/OhiMyMind** (**public**). Local dump `z/ohimymind/`. Do not nest Oh!MyMind in `askred-dot-ru/morda` or `law-bot`.
- **Source:** published 2026-09-17.

## 2026-09-17 — v1 contour (locked)

- **Scope:** first delivery.
- **Rule:**
  - Web app (FastAPI + React), PostgreSQL, own login/password.
  - `pgvector` in schema now; embedding **provider and job later**.
  - No 1C in v1 (no tables, routes, env). Later hypothetical: outbound HTTP from Oh!MyMind.
  - Dev: Docker Compose (API, IMAP worker, Postgres+pgvector). Config **only via env** so the same app can later run on the host without Docker (`DATABASE_URL`, `ATTACHMENTS_DIR`, bind host/port).
  - Mail: Yandex app-password, Gmail OAuth in browser; full local copy; IDLE; unified folder tree (per-mailbox split optional); delete → Trash + `\Deleted`, EXPUNGE on empty trash; thread reading pane on the right; attachments on disk.
- **Source:** user decisions, 2026-09-17.
