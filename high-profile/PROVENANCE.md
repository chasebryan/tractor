# Provenance and publication

```text
claim → claim version → claim_evidence → evidence fragment
                                           ↓
                                      source snapshot
                                           ↓
                                         source → publisher
```

Only `published=true` versions appear in the public research API. A reviewer supplies a subject, predicate, statement, normalized value, classification, confidence factors, dates, notes and explicit evidence links. The publication service validates the candidate, opens one transaction, creates its version and evidence links, asks the database to publish, and records an audit event and information-change event. Any failure rolls the entire publication back.

The schema enforces a supporting evidence chain independently of application code. Contradictory sources may coexist with supporting sources. No source tier automatically overrides another. Revision numbers and a supersession pointer preserve the earlier evidence and confidence.

## Classification and confidence

Classifications are DOCUMENTED, OFFICIALLY_STATED, ASSESSED, ESTIMATED, REPORTED, DISPUTED, UNVERIFIED, HISTORICAL, SUPERSEDED and RETRACTED. Confidence is a separate field: VERY HIGH, HIGH, MODERATE, LOW or INSUFFICIENT.

The confidence inspector exposes authority, independence, directness, recency and limitations. These are reviewer-authored explanations, not a probability model. “High” confidence in an attributed official statement does not independently verify the underlying inventory. Shared authorship or publisher groups do not count as independent corroboration.

## Retained text and hashes

An original excerpt is labeled as such and carries its language. A paraphrase is labeled **editorial paraphrase**, not disguised as original source text. Translation is a separate row with engine, model, language, review status and optional confidence. Original material is never replaced by a translation.

The seed preserves only short excerpts and paraphrases. Its SHA-256 values are hashes of local fragment manifests, not original full documents. The retrieval note states this limitation. Manual ingestion hashes the exact submitted UTF-8 text and records that it was submitted, not fetched automatically.

Historical availability, not historical omniscience: the seed's actual ingestion dates are the time it was loaded. Searching public evidence as of 2024 can return a 2024 publication; searching system knowledge before ingestion returns no claims.
