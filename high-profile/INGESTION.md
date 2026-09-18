# Ingestion

Index includes a functioning **manual text ingestion and review service**, exercised by integration tests. Scheduled acquisition, source-specific scraping, machine extraction and automated translation are not enabled.

`ManualSourceProvider` validates records against a common `SourceDocument` schema. It requires title, public HTTPS URL, an existing publisher UUID, publication date, BCP-47-style language, document type, dataset version, license, original text, source location and explicit synthetic status. Unknown fields are rejected. Submitted text is retained literally, including suspicious instructions; it is never executed or sent to a model.

`ingestDocument()` records a running ingestion job, stores content using `DocumentStore`, then atomically creates a source, retrieval snapshot and evidence fragment. Success produces **REVIEW**, not published intelligence. Failure is recorded as **FAILED** without a partial database provenance chain. Local content is content-addressed; a failed database transaction may leave an unreferenced content object, which can be collected during maintenance after checking references.

`publishReviewedClaim()` validates a complete reviewer-authored candidate and publishes atomically. It is available through the token-protected `POST /api/review/claims`. This is a deliberate editorial gate, not a mechanism for publishing generated statements automatically.

## Providers and independence

`DiscoveryProvider` returns candidates only. `TractorProvider` wraps an injected search client and validates returned public URLs; HIGH-PROFILE does not import Tractor code or require a Tractor deployment. The client is not configured in this release. Use the same interface for IAEA, SIPRI, FAS, UN, government, academic and news discovery providers when their permitted APIs and licensing are established. Do not add empty adapters that claim to have ingested data.

`DocumentStore` abstracts `put` and `get`. `LocalDocumentStore` uses validated SHA-256 keys, restrictive file modes and no user-supplied paths. A production object-store adapter must preserve equivalent immutability, authorization and checksum semantics.

## Acquiring future sources

Future network acquisition must separately implement DNS resolution and private-address rejection, redirect validation at every hop, response-size and time limits, content-type validation, origin allowlists, licensing checks, robots/terms compliance, rate limiting and bounded retries. URL validation alone is **not** DNS-rebinding-safe fetching. No current ingestion path fetches arbitrary URLs.

Maintain each source's original language. Store translations separately with engine/model and uncertainty. Treat all text and source metadata as data, including strings that resemble model instructions. Preserve documents according to copyright permissions; the included reference fixtures retain only short passages or clearly labeled paraphrases.

Job statuses include QUEUED, RUNNING, REVIEW, FAILED and COMPLETE. Index records each manual attempt. Scheduling, automatic retries, cross-job recovery and source-diff processing belong to Watch phase 2 and are not represented as active services.
