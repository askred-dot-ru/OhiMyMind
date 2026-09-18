# Delta for mail-stream

## MODIFIED Requirements

### Requirement: Compose reply drafts flags search

The system MUST support compose, reply (From = source account), forward, drafts (IMAP Drafts + local), `\Seen`/`\Flagged`, and folder FTS (`GET /mail/threads` `q` on subject+body via `plainto_tsquery('simple')`). HTML compose is required; the UI MUST sanitize HTML on display with DOMPurify.

The mail list chrome omnibar (placeholder «Поиск знаний, писем, тегов») MUST submit to `GET /api/v1/search` with default `mode=hybrid` over the caller's eligible indexed folders, not as a folder-only FTS of the current list. Clicking a hit MUST open that identifier thread in the right pane. Inbox important/unimportant bucket search inputs MUST remain local filters of that section's thread heads (not hybrid).

#### Scenario: Reply from unified inbox
- GIVEN a Gmail message in unified Inbox
- WHEN the user replies
- THEN SMTP and IMAP Sent use the Gmail account, not a different default

#### Scenario: Folder FTS token
- GIVEN a stored body containing a unique token and GET threads with `q` equal to that token
- WHEN the request is scoped to that message's folder
- THEN that thread is returned to the owner

#### Scenario: Omnibar hybrid
- GIVEN an indexed Inbox letter whose body discusses a topic without sharing a rare FTS token with the query
- WHEN the user submits a natural-language query in the list omnibar
- THEN `/api/v1/search` hybrid returns that thread among hits
- AND choosing a hit opens the thread pane

## Context sources

Omnibar copy and inbox buckets: `web/src/pages/Mail.tsx`. Folder FTS: `app/routers/mail.py` `plainto_tsquery`.
