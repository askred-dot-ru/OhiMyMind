# Delta for mail-stream

## ADDED Requirements

### Requirement: Account providers

A user MUST connect one or more accounts of type `gmail` (OAuth browser flow) or `yandex` (application password). Multiple accounts per user are allowed. Default compose account is exactly one per user (first connected, then user-selectable).

#### Scenario: Yandex connect
- GIVEN a logged-in user and IMAP reachable
- WHEN they POST account `provider=yandex` with app password
- THEN the worker can IDLE INBOX
- AND the password is stored encrypted, not in plaintext columns

#### Scenario: Gmail without OAuth env
- GIVEN `GOOGLE_OAUTH_CLIENT_ID` is empty
- WHEN the user starts Gmail connect
- THEN the API returns 409 `gmail_oauth_not_configured`
- AND no partial account row is left active

#### Scenario: Gmail with OAuth env
- GIVEN OAuth env and a Google consent success
- WHEN the callback completes
- THEN a `gmail` account exists with a refresh token in the encrypted blob

### Requirement: Unified folder tree

Accounts with `unified=true` MUST share one canonical folder tree for that user, merging folders by case-insensitive name. An account with `unified=false` MUST appear as a separate tree labeled by email.

#### Scenario: Two unified inboxes
- GIVEN user has Yandex and Gmail both `unified=true`
- WHEN they open Inbox
- THEN messages from both accounts appear in one Inbox list
- AND each message retains `account_id`

#### Scenario: Split account
- GIVEN one account `unified=false`
- WHEN they list folders
- THEN that account's Inbox is a separate node, not merged

### Requirement: Full copy and attachments

The worker MUST store headers, text, HTML, flags, and download attachments to `ATTACHMENTS_DIR`. A missing attachment file MUST be a sync error on that message, not a silent skip of the whole mailbox.

#### Scenario: Message with attachment
- GIVEN a new IMAP message with one PDF
- WHEN sync completes
- THEN `mail_attachments` has filename, mime, size, sha256
- AND GET `/api/v1/mail/attachments/{id}` returns the bytes for the owner

### Requirement: Threads in the reading pane

The UI MUST group messages by thread. Selecting a thread head in a folder list MUST show the full thread on the right in chronological order.

Threading MUST be the connected component of RFC `Message-ID`, `In-Reply-To`, and `References` only, walked recursively; existing threads that share an identifier MUST merge. The system MUST NOT glue messages by normalized subject or by participants. API process start MUST run `rebuild_all_threads` so previously subject-glued piles are split. Archive still parks the whole identifier thread; a later inbox reply that shares identifiers MUST resurface that chain, not unrelated same-subject mail.

#### Scenario: Reply chain
- GIVEN messages M1 (inbound), M2 (reply), M3 (reply) linked by In-Reply-To
- WHEN the user selects M2 in the list
- THEN the right pane shows M1, M2, M3
- AND selecting M1 or M3 shows the same set

#### Scenario: Same subject is not a thread
- GIVEN two inbox messages with the same subject and no shared Message-ID / In-Reply-To / References
- WHEN the user opens either
- THEN the right pane shows only that message's identifier component
- AND the other message stays a separate thread head

### Requirement: Delete and empty trash

UI delete MUST move the message to canonical trash and set IMAP `\Deleted` on the source. Empty trash MUST EXPUNGE the trash folder for the affected accounts.

#### Scenario: Delete
- GIVEN a message in Inbox
- WHEN the user deletes it
- THEN it is absent from Inbox and present in Trash
- AND the IMAP source message is `\Deleted` or moved per provider map

#### Scenario: Empty trash
- GIVEN messages in Trash
- WHEN the user empties trash
- THEN local trash is empty
- AND IMAP EXPUNGE ran on those accounts' trash folders

### Requirement: Archive from Inbox

Archive MUST apply the provider map in design D10 (Gmail: remove INBOX label; Yandex: move to Archive folder).

#### Scenario: Archive
- GIVEN a message in Inbox
- WHEN the user archives it
- THEN it is absent from Inbox
- AND it is listed under Archive

### Requirement: IDLE freshness

The worker MUST use IMAP IDLE on INBOX. The UI MUST poll thread lists at 5 seconds. New INBOX mail MUST appear within 5 seconds after the worker committed the row.

#### Scenario: New mail
- GIVEN IDLE is connected
- WHEN a new message arrives in INBOX
- THEN the worker writes it before the next 5s UI poll
- AND the list shows the thread head

### Requirement: Compose reply drafts flags search

v1 MUST support compose, reply (From = source account), forward, drafts (IMAP Drafts + local), `\Seen`/`\Flagged`, and FTS search (`q` on subject+body). HTML compose is required; the UI MUST sanitize HTML on display with DOMPurify.

#### Scenario: Reply from unified inbox
- GIVEN a Gmail message in unified Inbox
- WHEN the user replies
- THEN SMTP and IMAP Sent use the Gmail account, not a different default

#### Scenario: Search
- GIVEN a stored body containing a unique token
- WHEN GET threads with `q` equal to that token
- THEN that thread is returned to the owner

### Requirement: Inbox important and unimportant

Canonical Inbox MUST split the thread-head list into two sections: **Важные** then **Не важные**. A thread is unimportant when the exact From-domain (case-insensitive, host after `@`) is in that user's `users.unimportant_domains` JSONB list; otherwise it is important. Each section has its own search and domain tabs. Settings MUST CRUD the same list. HTTP: `GET`/`PUT`/`POST /api/v1/mail/unimportant-domains`, `DELETE /api/v1/mail/unimportant-domains/{domain}`.

#### Scenario: Domain moves to unimportant
- GIVEN an inbox thread whose From-domain is `news.example`
- WHEN the user marks that domain unimportant
- THEN that thread (and other inbox heads from `@news.example`) appear only in **Не важные**
- AND other domains stay in **Важные**

### Requirement: Unimportant dock and clear

If any unimportant inbox heads exist, a frosted dock at the bottom of the list pane MUST show the Russian plural count. Clicking the count raises the list: if all tiles fit, the last unimportant tile aligns to the pane bottom (top spacer); if not, the unimportant heading sticks to the pane top and the leftover tail is scrolled by hand. A down control on the dock restores `scrollTop=0`. Scrolling back to the important section also lowers the dock state.

Button **Очистить** sits to the right of heading **Не важные** (above that section's search). One `window.confirm`, then `POST /api/v1/mail/inbox/unimportant/clear` parks every inbox message whose From-domain is in `unimportant_domains` into trash. Split-folder account prefixes MUST be respected. Important inbox mail and non-inbox folders MUST NOT be trashed.

#### Scenario: Clear unimportant
- GIVEN inbox mail from unimportant domains and from other domains
- WHEN the user confirms Очистить
- THEN unimportant inbox messages are in Trash
- AND important inbox messages remain

### Requirement: Tile context menu and Shift range

Each thread tile MUST open a context menu on right-click: Reply, Forward, Delete, Archive, Execute, and in Inbox **В не важное** / **В важное**. Menu actions that need a message use the tile's latest message by time.

Shift+click MUST select an inclusive range in **displayed** list order (Inbox: visible important heads, then visible unimportant heads; other folders: the visible list). Shift+click MUST NOT open the thread. A normal click selects one tile and opens it. Right-click on an unselected tile resets the selection to that tile; right-click on a selected tile keeps the multi-selection. Selected tiles use class `picked` (distinct from `active`).

Delete, Archive, Execute, and Inbox importance MUST apply to the whole selection. Unique From-domains of the selection are marked important or unimportant. Reply and Forward apply only to the tile the menu opened on. Delete MUST confirm once for N letters (`Удалить это письмо?` / `Удалить N письма|писем?`).

#### Scenario: Shift two tiles then archive
- GIVEN two adjacent visible inbox heads
- WHEN the user clicks the first, Shift+clicks the second, then right-clicks a selected tile and chooses Archive
- THEN both threads are parked to Archive
- AND one menu action is enough

#### Scenario: Reply stays single
- GIVEN two selected tiles
- WHEN the user right-clicks tile B and chooses Reply
- THEN compose opens for B's latest message only

### Requirement: Per-letter pane actions and Execute

In the right pane, Reply / Forward / Delete apply to **that** letter. Archive parks every message in the identifier thread. **Выполнить** (`POST /api/v1/mail/messages/{id}/done`) is temporary: it forwards the invoked letter to hardcoded `DONE_RECIPIENT` (`robr@askred.ru`, not a setting) then archives the whole thread. There is no sticky thread toolbar.

#### Scenario: Execute
- GIVEN an open thread
- WHEN the user clicks Выполнить on message M
- THEN an outbox row forwards M to `robr@askred.ru`
- AND the whole thread is absent from Inbox and listed under Archive

### Requirement: Attachment gallery and file tiles

CID images belong in the HTML body. Other raster attachments (`jpg`/`jpeg`/`png`/`gif`/`webp`/`bmp`/`avif`, `image/*` except SVG/XML, size ≤ 8 MiB) MUST render as an in-body gallery; click opens inline (`GET /api/v1/mail/attachments/{id}`). Remaining files MUST sit in a wrapping horizontal tile row: type glyph, name, size, message date; tile click opens inline; a download control uses `GET /api/v1/mail/attachments/{id}?download=1` (`Content-Disposition: attachment` and filename). SVG and oversize rasters are file tiles, not gallery.

#### Scenario: Mixed attachments
- GIVEN a message with a 200 KiB PNG (not CID) and a PDF
- WHEN the user opens the message
- THEN the PNG is in the gallery
- AND the PDF is a file tile with a download control

### Requirement: HTML frame without inner scroll stripe

Sanitized HTML MUST render in an iframe (`scrolling=no`) whose height grows to the content (content height + 8px). Inner `html`/`body` MUST hide overflow and scrollbars. The frame background MUST match the pane (`--bg-2`), including dark theme, so no light scrollbar gutter appears beside pane actions.

#### Scenario: Dark HTML letter
- GIVEN a dark UI theme and an HTML body
- WHEN the letter is shown
- THEN the iframe has no inner scrollbar
- AND no light stripe appears next to Выполнить

## Context sources

Verified in repo (not 1C): `app/threads.py` identifier-only + `rebuild_all_threads` on API start; `users.unimportant_domains` Alembic `003`; `app/routers/mail.py` domain CRUD, clear, done, `download` query; `web/src/pages/Mail.tsx` buckets/dock/Shift `picked`; `web/src/MsgAttachments.tsx`; `web/src/EmailHtml.tsx`. `recall` 610–616. Graph/code MCP skipped (not 1C sources).
