# Tasks: mail-stream-v1

## 1. Scaffold

- [x] 1.1 Python package layout: `app/` (API), `worker/`, `web/` (Vite React), `alembic/`, `.env.example`, `.gitignore` already covers secrets
- [x] 1.2 `docker-compose.yml`: `db` (`pgvector/pgvector:pg16`), `api`, `worker`; env from `.env`; volume for `ATTACHMENTS_DIR`
- [x] 1.3 Dockerfile for API (installs `web/dist`) and worker (same image, different command)

## 2. Schema

- [x] 2.1 Alembic: `CREATE EXTENSION vector`; tables `users`, `knowledge_items`, `topics`, `item_topics`, `distribution_routes`, `mail_accounts`, `mail_account_secrets`, `mail_folder_maps`, `mail_threads`, `mail_messages`, `mail_attachments`, `mail_outbox`
- [x] 2.2 `knowledge_items.embedding vector(1536)` nullable; `stream_kind` check includes mail/messenger/llm_session
- [x] 2.3 No `user_1c_*` tables
- [x] 2.4 Alembic `002_attachment_cid`; `003_unimportant_domains` (`users.unimportant_domains` JSONB)

## 3. Auth and ACL

- [x] 3.1 Bootstrap admin from env; argon2id; session cookie `ohimymind_session`
- [x] 3.2 Routes register / login / logout / me
- [x] 3.3 Owner filter; admin `as_user_id` read-only; compose-as-other → 403

## 4. Mail worker

- [x] 4.1 Encrypt secrets with `APP_MASTER_KEY`; Yandex app password connect
- [x] 4.2 Gmail OAuth start/callback; 409 if Google env empty
- [x] 4.3 IDLE INBOX + 60s folder sweep; full copy; attachments on disk
- [x] 4.4 Canonical folder map D10; unified vs split trees
- [x] 4.5 Thread linking D11; outbox SMTP + APPEND Sent
- [x] 4.6 Trash / EXPUNGE / archive per D10; flags `\Seen` `\Flagged`; drafts

## 5. API

- [x] 5.1 Implement D14 routes except none for 1C
- [x] 5.2 FTS `q`; attachment download; health 200/503
- [x] 5.3 GET `/api/v1/onec/*` is not registered (404)

## 6. React UI

- [x] 6.1 Login / register
- [x] 6.2 Account settings (Yandex form, Gmail button, unified toggle, default From)
- [x] 6.3 Folder tree, thread list (5s poll), right-pane thread, DOMPurify HTML
- [x] 6.4 Compose / reply / forward / delete / empty trash / archive / search / flags
- [x] 6.5 Identifier-only threading + `rebuild_all_threads` on API start (no subject/participant glue)
- [x] 6.6 Inbox important / unimportant (`users.unimportant_domains`), settings CRUD, dock, Очистить
- [x] 6.7 Tile RMB menu; Shift range + batch archive/delete/execute/importance; Reply/Forward single
- [x] 6.8 Per-letter pane actions; temporary Выполнить → `DONE_RECIPIENT` then archive thread
- [x] 6.9 Attachment gallery + file tiles; `?download=1`
- [x] 6.10 HTML iframe: no inner scrollbars, height to content, frame `--bg-2`

## 7. Verify

- [x] 7.1 `docker compose up --build`: `/health`, `/`, register+login
- [x] 7.2 Yandex or Gmail: unified Inbox, thread pane, delete→Trash
- [x] 7.3 Confirm no 1C env/routes in the running image

## Context sources

`recall` 585–588, 590, 610–616. Specs in this change. No 1C MCP for implementation tasks.
