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

The UI MUST group messages by thread. Selecting any message in a folder list MUST show the full thread on the right in chronological order.

#### Scenario: Reply chain
- GIVEN messages M1 (inbound), M2 (reply), M3 (reply) linked by In-Reply-To
- WHEN the user selects M2 in the list
- THEN the right pane shows M1, M2, M3
- AND selecting M1 or M3 shows the same set

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
