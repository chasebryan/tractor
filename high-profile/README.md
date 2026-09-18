# HIGH-PROFILE

**Global Nuclear Capabilities Intelligence**  
Every claim has evidence. Every change has a history.

HIGH-PROFILE Index is a working, evidence-led research application. It provides searchable country, programme, facility, delivery-system and treaty profiles; a Source Ledger; confidence explanations; contradictory evidence; immutable assessment versions; and saved, cited investigations.

## Run locally

Use Node.js 22 or later and pnpm 11.

```sh
pnpm install --frozen-lockfile
pnpm dev
```

Open **http://127.0.0.1:4310**. The development server creates a disk-persistent PostgreSQL database using PGlite in `.data/postgres`, applies migrations and loads the development collection once. No accounts, model API keys, Docker, Tractor or external database are needed for this local workflow.

For a conventional PostgreSQL server, set `DATABASE_URL` before starting. Both adapters use the same PostgreSQL SQL, transactions and migrations. Local PGlite permits one process per database directory; stop the app before running database CLI tools against it. All in-memory tests use isolated databases.

## Try the research workflow

1. Search **China**. Open a claim or its evidence link.
2. Inspect the source, publication date, confidence rationale and original reference.
3. Open **Chinese nuclear forces**, then choose **History** in its evidence inspector. Select version 1 to see the earlier assessment and its evidence.
4. Set the profile's public-evidence date to **2024-12-31**. The later revision disappears; the earlier one remains.
5. Open **Illustrative fuel-cycle programme** to inspect a clearly labeled fictional disagreement.
6. Open France's historical statement to compare a short French excerpt with the editorial translation.
7. Save a version to an investigation, reload, then export a Markdown research collection with original citations.

## What the data represents

The included collection contains **14 entities, 16 claims, 17 claim versions and 7 sources**. Five source records reference publicly verified publications from SIPRI, ENEC, the French presidency and the UN Treaty Collection. Two are entirely synthetic test documents. All screens label the collection as development data.

Public references cover selected historical facts through 2025. They are **not a current or comprehensive global assessment**. Older sources retain lifecycle notices. Short original excerpts are distinguished from editorial paraphrases; snapshot hashes cover only the retained material, not an unarchived original webpage. Retrieval records describe exactly what was verified and entered.

## Verification

```sh
pnpm build
pnpm test
pnpm test:production
# Keep pnpm dev running in another terminal:
pnpm exec playwright install chromium
pnpm test:ui
# With the application stopped when using embedded PostgreSQL:
pnpm db:audit
```

Tests cover API contracts, PostgreSQL constraints and rollback, publication guards, contradictions, temporal reconstruction, multilingual data, entity resolution, ingestion validation, filesystem persistence, investigations, cross-origin protections, authorization, desktop/mobile flows and automated WCAG checks. See [VERIFICATION.md](VERIFICATION.md) for the measured results from this build.

## Release scope

Implemented: the **Index** milestone, a local record-change log, manually submitted document ingestion primitives, reviewer-authorized claim publication, generic discovery/storage interfaces, and a small finished investigation workflow.

Not active: scheduled scraping, live monitoring, AI extraction/translation, automated contradiction detection, a comprehensive world database, multi-user authentication, external object storage, or Atlas. These later phases are not simulated. The Tractor adapter is an injected discovery interface; no Tractor service is contacted.

Production mode protects private research and mutation APIs with a server-side reviewer token, disables automatic seed loading, uses a restrictive content security policy and serves the built UI. A shared production deployment needs a configured PostgreSQL service, TLS and an authentication gateway. The token belongs behind that gateway, never in browser source. See [DEPLOYMENT.md](DEPLOYMENT.md).

## Project guide

- [ARCHITECTURE.md](ARCHITECTURE.md) — components, trust boundaries and decisions
- [DATA_MODEL.md](DATA_MODEL.md) — relational and temporal model
- [PROVENANCE.md](PROVENANCE.md) — publication rules and confidence
- [SEARCH.md](SEARCH.md) — filters and transparent query interpretation
- [API.md](API.md) — routes, parameters and errors
- [INGESTION.md](INGESTION.md) — manual documents and discovery providers
- [SOURCE_POLICY.md](SOURCE_POLICY.md) — evidence, independence, rights and lifecycle
- [SAFETY.md](SAFETY.md) — research boundaries
- [DEVELOPMENT.md](DEVELOPMENT.md) — local commands and tests
- [DEPLOYMENT.md](DEPLOYMENT.md) — production setup, backup and limitations
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution requirements

The application is independent of Tractor. **Tractor finds. HIGH-PROFILE understands.**
