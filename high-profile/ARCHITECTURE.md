# Architecture

## Runtime

React 19 and TypeScript render a client application using React Router. Vite provides local development and builds static assets. Express 5 serves the API and built assets from one origin. The browser never opens a database connection or receives a reviewer credential from environment variables.

`server/db.ts` exposes a small SQL/transaction adapter for node-postgres and PGlite. `DATABASE_URL` selects a conventional PostgreSQL service. Without it, PGlite runs PostgreSQL in WebAssembly with filesystem persistence. This is the same SQL engine family, not an in-memory JavaScript imitation or SQLite translation. PGlite is appropriate for one local process; use a PostgreSQL service for concurrent production workloads.

```text
React workspace → same-origin Express API → PostgreSQL
                                ↓
                         immutable provenance
Manual document → validated source + snapshot + fragment → review
Human-reviewed candidate → atomic publication → version + audit + change event
Discovery provider → candidate URL/title only → future acquisition stage
```

## Code ownership

| Module                | Responsibility                                                     |
| --------------------- | ------------------------------------------------------------------ |
| `src/main.tsx`        | App shell, routing, notifications and navigation                   |
| `src/components.tsx`  | Shared search, claim list, dates, badges and timelines             |
| `src/pages.tsx`       | Research views and investigation workflow                          |
| `src/inspector.tsx`   | Evidence, confidence, pinned versions and save controls            |
| `src/api.ts`          | Abortable API reads and error handling                             |
| `server/app.ts`       | Validated routes and request security boundaries                   |
| `server/search.ts`    | Parameterized SQL and bounded query interpretation                 |
| `server/ingestion.ts` | Document normalization, storage, resolution and review publication |
| `server/audit.ts`     | Provenance and data-quality checks                                 |
| `server/seed.ts`      | Explicit, repeatable reference collection                          |

## Decisions

1. **Claims are atomic.** Entity profiles are catalogue identities, not unqualified bags of capabilities. Assertions appear as versioned claims with supporting evidence.
2. **Relational graph first.** Typed entities and reusable relationship predicates avoid a separate graph database. Country codes are constrained by a catalogue; entity aliases remain language-aware. Ambiguous aliases are returned for review.
3. **Append-only knowledge.** Published versions, source records, retrieval snapshots, evidence, translations, publisher identity and audit records cannot be rewritten through normal SQL operations. Changes create new versions and events.
4. **No model in the source-of-record path.** Search interpretation is deterministic and visible. No OpenAI or other AI key is required. External text is never interpreted as a command or prompt.
5. **Single local research workspace.** Investigations persist in PostgreSQL. Multi-user permissions require a future identity layer. Production research APIs are token-protected and designed to sit behind an authenticated gateway.
6. **No speculative infrastructure.** No Redis, OpenSearch, Neo4j or scheduler is introduced before the workload calls for it. Manual ingestion has explicit jobs and errors; automatic acquisition is a later release.

## Operational limits

This is a small initial index, not a high-volume global crawler. Search is bounded and paginated; current joins are appropriate for the seed collection. Before loading a large corpus, benchmark a maintained search-document table combining entity, alias and claim terms and add query-plan regression tests. No load-testing or high-availability claim is made for this release. Read [DEPLOYMENT.md](DEPLOYMENT.md) before exposing it beyond localhost.
