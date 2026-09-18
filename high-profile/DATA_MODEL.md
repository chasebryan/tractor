# Data model

All substantive records use durable UUIDs. Human-readable slugs are navigation aids, never identity keys.

## Tables

| Group      | Tables                                                              | Purpose                                                                             |
| ---------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Catalogue  | `countries`, `entities`, `aliases`                                  | ISO-code catalogue, typed identities, multilingual aliases                          |
| Sources    | `publishers`, `sources`, `source_snapshots`                         | Publisher tier/independence, bibliographic identity, exact retrieval metadata       |
| Evidence   | `evidence_fragments`, `translations`, `claim_evidence`              | Retained source material, separate translations, SUPPORTS/CONTRADICTS/CONTEXT links |
| Knowledge  | `claims`, `claim_versions`, `assessments`, `claim_contradictions`   | Stable predicates, immutable revisions, assessments, explicit disagreements         |
| Graph      | `relationships`                                                     | Typed directed links with an optional supporting claim                              |
| Research   | `users`, `investigations`, `investigation_items`, `saved_searches`  | Future user identity seam and current persistent research collections               |
| Operations | `ingestion_jobs`, `watch_events`, `audit_logs`, `schema_migrations` | Processing history, information changes and migration provenance                    |

The `entities.kind` enum supports Country, Organization, Program, Facility, Weapon System, Delivery System, Reactor, Fuel-Cycle Capability, Treaty, Agreement and Event. Claims, sources, fragments, assessments, investigations and publishers have their own tables. This satisfies the entity taxonomy without duplicating the same identity schema into many parallel tables.

`value` is a normalized JSON value. A delivery-system nuclear role is explicitly represented by `NUCLEAR_CAPABLE`, `ASSESSED_NUCLEAR_ARMED` or `CONFIRMED_NUCLEAR_ROLE` where evidence supports it. The fixture only supplies a historically attributed component-level role; it does not infer individual platform armament.

## Time dimensions

| Field                             | Meaning                                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `effective_from`, `effective_to`  | Time described by an assessment; an absent end date is not an assertion of continuing current validity |
| `public_on`                       | Earliest date this particular assessment version can be reconstructed from its cited material          |
| `sources.published_on`            | Bibliographic publication date                                                                         |
| `source_snapshots.retrieved_at`   | When retained material entered this collection                                                         |
| `evidence_fragments.extracted_at` | Extraction/entry time                                                                                  |
| `claim_versions.recorded_at`      | Knowledge ingestion time                                                                               |
| `reviewed_at`                     | Review timestamp for that immutable version                                                            |
| `claims.first_observed`           | First local registration of the claim identity                                                         |

`as_of` filters public and effective dates before selecting the latest eligible version. `known_at` separately bounds ingestion time. The UI labels the public reconstruction explicitly. Version 1 does not acquire the classification or confidence of version 2. The supersession pointer links revisions within the same claim only.

## Integrity rules

- Foreign keys preserve every link in the provenance chain.
- A database trigger rejects publication without dated supporting evidence and its source, snapshot and publisher.
- Publication rejects synthetic evidence attached to a claim presented as non-synthetic.
- Effective intervals cannot run backward. Retrieval cannot precede publication; extraction cannot precede retrieval; a version cannot predate its evidence extraction.
- Published claim versions and their evidence links are immutable; direct evidence/source deletion is rejected.
- Exact duplicate fragments and repeated investigation-version saves are constrained.
- Country codes must be in the `countries` catalogue. The initial catalogue contains real ISO codes; adding entries requires review, since format validation alone cannot establish ISO membership.
- A synthetic disagreement is permitted and retained. The audit does not treat an explicit, linked disagreement as corruption.

Entity aliases can collide across identities. This is detected by the audit and returned as `AMBIGUOUS`, never resolved by choosing the first row. Profile identity/description remains editorial catalogue context and is not a historical assertion. Claims carry the actual evidence history.
