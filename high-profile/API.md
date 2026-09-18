# API reference

Base URL: `http://127.0.0.1:4310/api`. JSON requests and responses use UTF-8. The application returns a request ID in `X-Request-ID`. Unknown API routes return JSON 404s, not the frontend HTML page. Validation failures return 400 with field paths; unexpected errors return a generic 500 and structured server log.

## Read routes

| Method and route                                                         | Parameters / result                                                                                   |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `GET /health`                                                            | Database connectivity and release/collection labels                                                   |
| `GET /meta`                                                              | Actual catalogue counts, countries and publishers                                                     |
| `GET /search`                                                            | Published claims, provenance, total, pagination, interpreted filters                                  |
| `GET /claims`                                                            | Alias of search                                                                                       |
| `GET /claims/:claimUUID`                                                 | Latest eligible version, all eligible versions, full evidence and contradictions                      |
| `GET /entities`                                                          | Catalogue identities; optional `q`, `kind`                                                            |
| `GET /entities/:UUID-or-slug`                                            | Dossier, aliases, claims and linked relationships; optional `as_of`, `known_at`                       |
| `GET /countries`                                                         | Country identities                                                                                    |
| `GET /facilities`                                                        | Facility and reactor identities                                                                       |
| `GET /programs`                                                          | Programme identities                                                                                  |
| `GET /systems`                                                           | Weapon- and delivery-system identities                                                                |
| `GET /countries/:id`, `/facilities/:id`, `/programs/:id`, `/systems/:id` | Profile aliases                                                                                       |
| `GET /sources`                                                           | Independent ledger; optional `q`, `health`, `language`, `publisher`                                   |
| `GET /sources/:sourceUUID`                                               | Bibliography, publisher, retrievals and linked published claim versions, including superseded history |
| `GET /timeline`                                                          | Published version history; optional `entity=UUID`                                                     |
| `GET /watch`                                                             | Actual local publication/change events; explicitly `automated_monitoring=false`                       |
| `GET /integrity`                                                         | Data-quality checks and lifecycle warnings                                                            |
| `GET /investigations`                                                    | Research collections, protected in production                                                         |
| `GET /investigations/:UUID`                                              | Saved exact versions and notes, protected in production                                               |
| `GET /investigations/:UUID/export`                                       | Downloadable cited Markdown collection, protected in production                                       |

There is no `/atlas` endpoint or scheduler pretending to be operational. Those interfaces belong to later releases.

### Search request

```text
GET /api/search?q=China&classification=ESTIMATED&min_evidence=1&limit=30
GET /api/search?kind=PROGRAM&country=CN&as_of=2024-12-31
GET /api/search?disputed=true&synthetic=true
```

Filters are documented in [SEARCH.md](SEARCH.md). `page` starts at 1 and `limit` is 1–100. `as_of` and `known_at` are inclusive calendar-day cutoffs. Claim detail also accepts `version=1` to choose an exact eligible version. A nonexistent version or one beyond a supplied date returns 404.

Every search item contains `claim_id`, version `id`, subject identity, statement, normalized `value`, classification, confidence, confidence factors, effective/public/recorded/reviewed dates, synthetic marker, supporting/contrary fragment counts, distinct independence groups and a provenance array. Each provenance entry contains source UUID, title, publisher, tier, URL, lifecycle, publication date, retrieval timestamp, snapshot UUID and evidence role.

### Error example

```json
{
  "error": "Invalid request parameters",
  "details": [{ "path": ["as_of"], "message": "Invalid calendar date" }]
}
```

## Research writes

Local development has a single researcher workspace. Production requires `Authorization: Bearer <REVIEW_TOKEN>` for all investigation operations. Invalid hostnames and cross-origin browser mutations are rejected. Tokens are server-side gateway credentials; the frontend does not embed them.

```text
POST /api/investigations
{ "title": "Civil nuclear milestones", "description": "Source review" }

POST /api/investigations/:UUID/items
{ "version_id": "a-published-version-uuid", "note": "Retain this evidence." }
```

Creation returns 201. Saving the same investigation/version pair is idempotent and updates its note. A missing investigation or unpublished version returns 404. Exports pin the saved evidence version, confidence explanation and original citations.

## Reviewed publication

`POST /api/review/claims` always requires the configured reviewer token, even during development. Without configuration it returns 503; an invalid credential returns 401.

The body matches `reviewSchema` in `server/ingestion.ts`:

```json
{
  "subject_id": "existing-entity-uuid",
  "predicate": "attributed_status",
  "statement": "An explicitly attributed statement from the supplied evidence.",
  "value": { "status": "documented" },
  "classification": "DOCUMENTED",
  "confidence": "HIGH",
  "confidence_rationale": {
    "authority": "Why the publisher is relevant.",
    "independence": "Shared and independent origins.",
    "directness": "How the passage supports the statement.",
    "recency": "Time limitations.",
    "limitations": "What remains uncertain."
  },
  "effective_from": "2025-01-01",
  "public_on": "2025-02-01",
  "evidence": [{ "id": "existing-evidence-uuid", "role": "SUPPORTS" }],
  "notes": "Reviewer reasoning and scope.",
  "is_synthetic": false
}
```

Replace the explanatory UUID strings with valid existing UUIDs. Add `claim_id` to append a revision; subject and predicate must match its stable identity. The database enforces provenance, temporal ordering, immutable history and fixture separation. Unknown fields are rejected. An integrity failure rolls back and is logged; it is never converted into a successful publication.

Manual document ingestion is currently a tested service interface, not an exposed upload endpoint. This avoids unauthenticated network fetching or file uploads before the acquisition/review UX is ready.
