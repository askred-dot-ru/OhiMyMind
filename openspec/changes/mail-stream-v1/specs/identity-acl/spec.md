# Delta for identity-acl

## ADDED Requirements

### Requirement: Local users

Users MUST authenticate with login and password stored in PostgreSQL (argon2id). The first admin MUST be created from `MYMIND_BOOTSTRAP_ADMIN` and `MYMIND_BOOTSTRAP_PASSWORD` when no admin row exists. Further users MAY self-register as role `user`.

#### Scenario: Bootstrap admin
- GIVEN an empty `users` table and bootstrap env set
- WHEN the API process starts
- THEN one admin user exists with that login
- AND the password is not written to logs

#### Scenario: Self-register
- GIVEN an existing admin
- WHEN an anonymous client POSTs `/api/v1/auth/register` with login and password
- THEN a `user` row is created with `role=user`
- AND a session cookie is issued only after a separate login (register does not auto-login)

#### Scenario: Login
- GIVEN a registered user
- WHEN POST `/api/v1/auth/login` with correct password
- THEN the response sets httponly cookie `mymind_session`
- AND GET `/api/v1/me` returns login and role

### Requirement: Ownership ACL

A `user` MUST only read and mutate mail owned by that user. An `admin` MUST read any user's mail via `as_user_id`. Admin MUST NOT send as another user in v1.

#### Scenario: User isolation
- GIVEN users A and B with disjoint accounts
- WHEN A lists threads without admin
- THEN B's messages are absent

#### Scenario: Admin inspect
- GIVEN an admin and user B
- WHEN admin GET `/api/v1/mail/threads?as_user_id=<B>`
- THEN B's threads are returned
- AND POST compose using B's `account_id` from the admin session is rejected (403)
