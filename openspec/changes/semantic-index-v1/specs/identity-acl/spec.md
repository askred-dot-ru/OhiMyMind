# Delta for identity-acl

## ADDED Requirements

### Requirement: Semantic search ACL

`GET /api/v1/search` MUST return only items whose `knowledge_items.owner_user_id` is the session user, unless the caller is `admin` and passes `as_user_id`. Admin MUST NOT gain send/compose rights through search. Hits MUST NOT include another user's mail.

#### Scenario: User isolation
- GIVEN users A and B with disjoint indexed mail
- WHEN A calls GET `/api/v1/search?q=...` without admin
- THEN B's items are absent

#### Scenario: Admin inspect
- GIVEN an admin and user B
- WHEN admin GET `/api/v1/search?q=...&as_user_id=<B>`
- THEN only B's matching items are returned

### Requirement: Index model is admin-only

`PUT /api/v1/index/model` and `GET /api/v1/index/models` and `POST /api/v1/index/retry-failed` MUST require `role=admin`. `GET /api/v1/index/status` MUST be allowed for any signed-in user; `indexed` / `eligible` / `failed` counts MUST be for that user (admin may use `as_user_id` to inspect another user's counts). A `user` PUT MUST return 403 and MUST NOT bump `embed_generation`.

#### Scenario: User cannot change model
- GIVEN a signed-in user with `role=user`
- WHEN they PUT `/api/v1/index/model`
- THEN the response is 403
- AND `app_settings.embedding_model` is unchanged

## Context sources

ACL pattern: archived identity-acl (`as_user_id` read-only). Model PUT admin: user lock 2026-09-18.
