# Deployment

## Local production build

```sh
pnpm build
pnpm start
```

The server serves built assets and APIs from one origin. Without `DATABASE_URL`, this remains a single-process local preview using the already-created embedded database. Production mode does not automatically seed an empty database. Set `SEED_FIXTURES=true` only for a deliberately labeled development/reference deployment.

## PostgreSQL deployment

Use the included Dockerfile and Compose configuration as a starting point. Supply a strong database password and reviewer token through your deployment secret manager:

```sh
export POSTGRES_PASSWORD='a-long-unique-database-password'
export REVIEW_TOKEN='a-long-unique-reviewer-token'
docker compose up --build
```

Compose binds the app to the host's loopback port 4310 and does not expose PostgreSQL. Its volume retains the database. Initial data is empty unless you explicitly choose `SEED_FIXTURES=true`. The Docker/PostgreSQL deployment recipe is supplied but is not claimed to have been exercised in an environment without Docker; see the verification report.

For internet/shared access, configure:

- Managed PostgreSQL with TLS, backups and a restricted application role. A migration owner applies DDL at startup; separate migration/application roles are a next deployment hardening step.
- A TLS reverse proxy/authentication gateway. Set `PUBLIC_ORIGIN` to the exact public origin so the API accepts that host.
- Per-user authentication/authorization at the gateway before forwarding any private research or review request. The current app provides one research workspace, not tenant isolation.
- A server-side `REVIEW_TOKEN`. The gateway may forward it as a Bearer token after authenticating the researcher. Never put it in JavaScript, local storage, URLs or the built bundle.
- Edge rate limits, request timeouts, and monitored structured logs. Public read APIs expose published claims plus catalogue/source metadata; unreviewed source metadata is not private. `/api/investigations` and review writes are protected in production.

The app does not trust arbitrary forwarded headers. The gateway should forward the configured host and normalize or remove an authenticated request's Origin only according to its own CSRF policy. Do not disable application checks to make a proxy appear functional.

## Backup and restore

Use PostgreSQL `pg_dump` and tested restores for a server database. Retain document storage objects with the corresponding snapshots. For embedded development, stop the app, copy the entire `.data/postgres` directory, then restart. Copying an active database directory is not a backup guarantee.

Migration failures must prevent startup. Take a backup before upgrades. Roll back the application only to a version compatible with the current schema; historical evidence is append-only and must not be dropped to reverse a UI deployment.

## Health and logs

`GET /api/health` checks database connectivity. `GET /api/integrity` checks provenance and data quality. HTTP logs include request IDs, route paths, status and duration; they omit authorization headers and bodies. Ingestion jobs retain failures. Publication logs identify the authorized reviewer role, not a per-person identity; integrate actual identities before multi-user editorial deployment.

Automated source monitoring, external object storage and large-corpus performance have not been deployed in this release. No uptime, throughput or comprehensive coverage claim is made.
