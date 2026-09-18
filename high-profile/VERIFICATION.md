# Release verification

Verified on 17 September 2026 (America/Chicago), using Node.js 24.19, pnpm 11.19, local PostgreSQL through PGlite, and Chromium. These results apply to the Index release and its development reference collection.

## Executed checks

| Check                                              | Result                         | Evidence                                                 |
| -------------------------------------------------- | ------------------------------ | -------------------------------------------------------- |
| Frozen dependency installation                     | Passed with the final lockfile | `pnpm install --offline --frozen-lockfile`               |
| TypeScript and optimized production build          | Passed                         | `pnpm build`; 308.92 kB JavaScript, 96.84 kB gzip        |
| Backend, database, API, search and ingestion tests | **37 passed**                  | [Backend results](verification/backend-tests.txt)        |
| Desktop and mobile browser workflows               | **12 passed**                  | [Browser results](verification/browser-tests.txt)        |
| Real production-process smoke test                 | **7 groups passed**            | [Production results](verification/production-smoke.json) |
| Data integrity                                     | **9 checks passed**            | [Integrity results](verification/integrity-audit.json)   |
| Dependency advisory audit                          | **0 reported advisories**      | [Registry audit](verification/dependency-audit.json)     |
| Formatting                                         | Passed                         | `pnpm format:check`                                      |

Backend coverage includes publication guards, immutable evidence/history, rollback, separate public/effective/knowledge dates, contradictions, multilingual text, ambiguous entity resolution, parameterized search, strict input validation, local storage path traversal, untrusted document text, failure recording, authorized publication and disk persistence. Tests use isolated databases and do not ingest from live services.

Browser coverage includes search, evidence inspection, source links, confidence rationale, historical revisions, contradictory and French-language evidence, Source Ledger filtering, empty states, responsive navigation, keyboard search and Escape, and saving/reopening a superseded version after reload. Both desktop (1440 × 1000) and mobile (390 × 664) layouts were inspected. See [desktop](verification/desktop.png) and [mobile](verification/mobile.png) screenshots.

Automated axe checks for WCAG 2 A/AA and 2.1 AA passed on the home page, entity directory, facility profile, Source Ledger, methodology page, investigation list and contradiction inspector at both tested sizes. Horizontal overflow was checked. These automated checks and keyboard workflows are not a complete screen-reader or formal WCAG conformance audit. A multi-page audit initially exceeded its 30-second test timeout; it passed after receiving a 90-second audit budget.

The production smoke test starts a separate server with a disposable disk database, loads the built SPA at a deep link, fetches its JavaScript/CSS assets, verifies the CSP, exercises search and integrity, rejects unauthorized private/review requests, creates and reads an authorized investigation, and rejects a cross-origin write. It cleans up its own database afterward. Run it with `pnpm build && pnpm test:production`; port 4312 must be free or set `SMOKE_PORT`.

## Security review

The completed [Codex Security report](security/report.md) records **no reportable findings across the 11 reviewed server files**. Independent baseline and architecture reviews were reconciled with the actual authorization, query, ingestion, storage and publication code. This is a scoped static review, not a guarantee that the application is vulnerability-free.

The report is sealed against its original snapshot. Documentation, frontend tests and package metadata changed while the audit ran, so the tool correctly recorded a directory-change warning. Server implementation remained unchanged during the review. [The audited server snapshot](security/audited-server.tar.gz) preserves the exact source anchors.

After that scan, both database CLI entry points were corrected to pass `DATA_DIR` through to the database adapter; the correction was exercised by seeding and auditing a separate selected directory while the main application remained open. The HTTP app received formatting-only changes. Deployment documentation now explicitly says unreviewed source catalogue metadata is public. A dependency audit identified a development-only Vitest advisory; upgrading to 4.1.11 cleared the audit, and all 37 backend tests passed again.

The security tool reported 7,700,390 aggregate tokens across four task rollouts, including 7,293,312 cached input tokens and 48,950 output tokens. These are tool-reported rollout totals, not an isolated measurement of security-review work or a billing estimate.

## Scope and remaining deployment work

- The seed is a small development collection of historical public references and clearly marked synthetic disagreement fixtures. It is not current global intelligence. Four stale/superseded/unknown source notices are expected and retained.
- Conventional PostgreSQL and Docker configuration are included, but no Docker engine or external PostgreSQL server was exercised here. PGlite runs real PostgreSQL locally, but adapter/deployment parity still needs an environment-specific check.
- Shared hosting needs PostgreSQL TLS/roles/backups, an identity/TLS gateway, proxy-origin integration and edge rate limits. The current workspace is shared, not tenant-isolated.
- No scheduled monitoring, automatic source fetching, AI extraction, full-source archival service, external object storage or Atlas is active. Those are later phases, as described in the build specification.
- Large-corpus performance, disaster recovery, concurrent editorial load and assistive-technology coverage have not been certified. The in-app browser preview could not consistently reach the local listener; the standalone Chromium tests and direct production HTTP checks succeeded.

The local server is a development process. If it stops, run `pnpm dev` from this project directory and open `http://127.0.0.1:4310`.
