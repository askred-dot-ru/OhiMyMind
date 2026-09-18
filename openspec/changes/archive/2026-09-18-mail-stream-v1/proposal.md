# Proposal: mail-stream-v1

## Why

Oh!MyMind is a **standalone** product: classification, storage, and distribution of knowledge streams. Mail is stream #1 — the simplest ingest, not the product. It has **no relationship to 1C** in this change. Later we may attach 1C by **outbound HTTP** from Oh!MyMind; URL and actions are unknown and are not designed here. Today: users, PostgreSQL copy of mail, IMAP IDLE, web UI with threads, envelope for later streams (messengers, LLM sessions).

## What changes

1. **Runtime:** Docker Compose with three processes — API (FastAPI + React static), IMAP/SMTP worker, PostgreSQL + `pgvector`. All endpoints and paths via env so the same app can later leave Docker.
2. **Identity:** users in Postgres (login/password). Role `user` sees only own mail; role `admin` can read others. No 1C user mapping.
3. **Knowledge envelope:** `knowledge_items.stream_kind ∈ {mail, messenger, llm_session}`; v1 writes only `mail`. Topics and distribution-route tables exist; v1 UI does not drive them.
4. **Mail stream:** Gmail (OAuth in browser) + Yandex (app password). Full local copy. Canonical folders Inbox/Sent/Drafts/Trash/Archive/Spam + user folders. Unified tree across a user's accounts by default; an account can opt out. Threads in the right pane **by Message-ID / In-Reply-To / References only** (no subject glue). Delete = Trash + `\Deleted`; EXPUNGE only on empty-trash. Attachments on disk; UI gallery + file tiles. Inbox split important / unimportant by From-domain, dock, clear-unimportant. Tile RMB menu; Shift range applies one menu action to N heads. Temporary Execute = forward to `robr@askred.ru` then archive thread.

## Scope

| In scope | Out of scope |
|---|---|
| Repo `z/ohimymind/`, GitHub `askred-dot-ru/OhiMyMind` | Any 1C configuration, CFE `Почта`, HTTP to 1C |
| Mail ingest/index/UI as above | Telegram / WhatsApp / Teams ingest (kind reserved) |
| LLM session kind reserved in DB | LLM chat UI, embeddings job, vector search UI |
| Env-ready run without Docker hostnames in code | Shipping a native installer in this change |
| Self-serve mailbox connect | ChatOps / commanding the agent from messengers |

## Approach

| # | Direction |
|---|---|
| 1 | Compose + migrations (`vector` extension, envelope + mail tables) |
| 2 | Auth, ACL, account secrets (env master key) |
| 3 | Worker: IMAP IDLE, folder map, full copy, SMTP send, Gmail XOAUTH2 / Yandex password |
| 4 | FastAPI JSON + React: login, folder list, message list, thread pane, compose/reply, flags, search FTS |
| 5 | Compose smoke (health, login, Yandex or Gmail) |

## Success criteria

- `docker compose up` yields a login page; a user can connect Yandex (app password) and/or Gmail (OAuth) and see a unified Inbox.
- Selecting any thread head shows the identifier-linked thread on the right (same subject alone does not join).
- Inbox lists important then unimportant; Shift+click + one RMB action archives/deletes/executes the range; Reply/Forward stay single.
- New mail arrives without refresh polling longer than IDLE latency + one API poll interval (≤ 5 s).
- Delete moves to Trash on server and locally; emptying Trash EXPUNGEs.
- Archive removes from Inbox per Gmail label / Yandex Archive folder map.
- No embedding provider is called; `embedding` column is NULL.
- No 1C client, tables, env keys, or API routes.
- Config works if `DATABASE_URL` and `ATTACHMENTS_DIR` point at a host Postgres and a host folder (documented; not required to demo without Compose).

## Risks

- Gmail IMAP requires a Google Cloud OAuth client in env; without it Gmail connect is disabled (explicit UI), Yandex still works.
- Full copy + HTML + attachments will grow disk; no retention in v1.
- IDLE drops on some providers; worker must reconnect with backoff.
- UNC path `//Mac/ai/z/ohimymind` needs `safe.directory` for git on Windows; unrelated to runtime.

## Context sources

Verified via MCP: `recall` 585–588, 590, 610–616. Standalone product; 1C IMAP/HTTP unused. `templatesearch` — no fitting template. Graph/code skipped.
