# Security gateway verification

This branch adds an isolated mesh.security_gateway module. It does not change the existing workflow execution path or enable a new HTTP route by default.

## Security model

- Only the send_email function is exposed to the model, with strict JSON schema and exact argument validation.
- Model output is a proposal, never authorization. Execution is a separate step requiring a short-lived, action-digest-bound, single-use approval token.
- SQLite BEGIN IMMEDIATE and a conditional update make approval consumption atomic across concurrent processes sharing the same database.
- Untrusted input provenance is persisted. Any taint ID attached to a proposal blocks email execution; this intentionally fails closed even if the model rewrites or paraphrases the untrusted text.
- SMTP is disabled unless MESH_EMAIL_SANDBOX=1; a recipient must exactly match MESH_EMAIL_ALLOWED_RECIPIENTS. TLS and SMTP authentication are mandatory.
- The module has no generic shell, filesystem, browser, or arbitrary HTTP tool.

## Authenticated runtime API

Run the separate gateway service with:

`python -m mesh.security_server`

It binds to 127.0.0.1:8091 by default. Put it behind a TLS-terminating reverse proxy before remote access. It requires two distinct high-entropy credentials:

- `MESH_GATEWAY_TOKEN`: proposal and execution endpoints
- `MESH_APPROVAL_TOKEN`: action approval endpoint

Endpoints:

- `POST /v1/propose` — gateway bearer token; accepts prompt and explicitly identified untrusted sources.
- `POST /v1/approve` — separate operator bearer token; accepts the exact proposed action and its digest, and returns a short-lived single-use approval token.
- `POST /v1/execute` — gateway bearer token plus the approval token; consumes the approval before attempting SMTP.

The approval credential is a high-impact secret. Only an operator-controlled approval interface should possess it. The API checks that the supplied digest matches the reviewed action; the operator interface must display the recipient, subject, body and digest before calling the approval endpoint. Do not expose the approval endpoint to model-generated content or ordinary end-user sessions.

## Required runtime configuration

Configure these as protected runtime secrets/environment values; never commit them or paste credentials into chat:

- OPENAI_API_KEY
- MESH_EMAIL_SANDBOX=1
- MESH_SMTP_HOST, MESH_SMTP_PORT (default 587)
- MESH_SMTP_USERNAME, MESH_SMTP_PASSWORD
- MESH_EMAIL_FROM
- MESH_EMAIL_ALLOWED_RECIPIENTS (comma-separated exact sandbox addresses only)

Use a dedicated email testing service/mailbox. Do not point this adapter at a production mail account. The exact allowlist is the final recipient boundary.

## Two-phase use

1. Call SecurityGateway.propose(prompt, untrusted_sources=[(source, text), ...]). This calls the real OpenAI Chat Completions endpoint and returns an action proposal and digest, not an email send.
2. A trusted approval interface must show the exact recipient, subject, body and digest to an operator. It then calls SecurityStore.create_approval(action, ttl_seconds=...) and retains the returned token securely.
3. Call execute_approved(action_data, approval_token, taint_ids=...). A tainted action is rejected. Otherwise, the approval is atomically consumed before SMTP is called.

Do not expose create_approval through an unauthenticated HTTP endpoint. A production approval interface needs a separately authenticated operator identity, CSRF protection if browser-based, rate limits, audit retention, and secret storage.

## Verification scope and limitations

Offline tests exercise parsing, taint persistence and action binding, approval binding/expiry/replay, SQLite concurrency, authenticated API boundaries, SMTP allowlisting/TLS behavior with a local test double, and adversarial tool-call payloads. These tests do not prove delivery through a live SMTP provider or availability/correctness of the live OpenAI service.

A live OpenAI check is opt-in with MESH_LIVE_OPENAI_TEST=1 and OPENAI_API_KEY; it makes a billable external request. A live email check is opt-in with MESH_LIVE_EMAIL_TEST=1 and MESH_EMAIL_TEST_RECIPIENT, plus a configured sandbox SMTP account; the recipient must exactly match MESH_EMAIL_ALLOWED_RECIPIENTS. Production resistance cannot be proven exhaustively; the evidence is limited to the stated test corpus, runtime configuration, and deployment environment.

## Current integration status

The module is additive and not yet wired into mesh/server.py. The existing /workflow endpoint remains unchanged and must not be treated as a secured tool-execution endpoint. Deployment is blocked until an authenticated approval boundary and the runtime secrets/provider configuration are installed and verified.
