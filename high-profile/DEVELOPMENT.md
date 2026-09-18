# Development

## Prerequisites

Node.js 22+, pnpm 11. Install exact dependencies with `pnpm install --frozen-lockfile`. Chromium is needed only for browser tests. Development uses one same-origin process; there is no frontend/backend port coordination.

```sh
pnpm dev                 # API + React on 127.0.0.1:4310
pnpm build               # TypeScript check + optimized Vite bundle
pnpm test                # Isolated PostgreSQL and HTTP integration tests
pnpm test:ui             # Desktop and mobile browser workflows
pnpm test:production     # Built server, disposable database, HTTP/security checks
pnpm format:check
```

Set `PORT` to change the listener. `HOST` is loopback-only in development. `DATA_DIR` selects a different embedded database directory for the server and both database CLI commands. `DATABASE_URL` selects node-postgres. `SEED_FIXTURES=false` starts without development records; `pnpm db:seed` explicitly seeds an empty catalogue. A nonempty catalogue is never overwritten. Build before running `test:production`; it uses a disposable database and port 4312 by default (`SMOKE_PORT` overrides it).

Environment files are examples, not automatically loaded. Export variables in your shell or use Node's `--env-file=.env` option before `--import tsx` in a customized run command. Never commit `.env` or production credentials.

## Testing

Vitest creates an isolated PostgreSQL engine and loads the fixture once. Each destructive assertion uses rollback or a separate record. The persistence test closes and reopens its own temporary disk database. Supertest exercises actual HTTP routing, validation and errors. Playwright uses a running server at `UI_BASE_URL` (default local port 4310). Browser tests create clearly named verification investigations. Prefer a separate test data directory/server to keep your research workspace clean.

For UI tests:

```sh
DATA_DIR=.data/ui-tests PORT=4311 pnpm dev
# in a second terminal
UI_BASE_URL=http://127.0.0.1:4311 pnpm test:ui
```

To use a system PostgreSQL instance in integration tests, extend the test harness with a disposable database and never point it at a real research corpus. The default tests do not access live external sources.

## Database maintenance

Stop the application before CLI operations on embedded PostgreSQL. `.data/postgres.lock` prevents a second process from opening it. After a crash, check that its recorded PID is no longer running before removing only that stale lock file. Do not remove a live lock. For a server database, normal PostgreSQL connection pooling supports concurrent processes.

Migration files are applied in numeric order inside transactions. Do not edit an applied migration; add another. Schema initialization should have one owner during deployment. Versioned claims and evidence must be changed through append-only services, not updates to published rows.

Use `pnpm db:audit` to check provenance, temporal chains, duplicates, aliases, metadata and translation completeness. Source-health warnings do not mean an integrity failure. Expected synthetic contradictions remain visible.
