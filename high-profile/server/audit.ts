import type { Database } from "./db.js";
export async function auditDatabase(db: Database) {
  const checks: Record<string, string> = {
    orphaned_published_claims: `SELECT v.id FROM claim_versions v WHERE v.published AND NOT EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ce.version_id=v.id AND ce.role='SUPPORTS')`,
    invalid_temporal_chains: `SELECT v.id FROM claim_versions v JOIN claim_evidence ce ON ce.version_id=v.id JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id WHERE s.published_on>v.public_on OR ss.retrieved_at>v.recorded_at OR ef.extracted_at<ss.retrieved_at`,
    synthetic_contamination: `SELECT v.id FROM claim_versions v JOIN claim_evidence ce ON ce.version_id=v.id JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id WHERE s.is_synthetic AND NOT v.is_synthetic`,
    alias_collisions: `SELECT normalized AS id FROM aliases GROUP BY normalized HAVING count(DISTINCT entity_id)>1`,
    duplicate_entities: `SELECT lower(name) AS id FROM entities GROUP BY lower(name),kind,country_code HAVING count(*)>1`,
    invalid_source_metadata: `SELECT id FROM sources WHERE title='' OR canonical_url !~ '^https://' OR language='' OR license=''`,
    invalid_country_codes: `SELECT code AS id FROM countries WHERE code !~ '^[A-Z]{2}$'`,
    failed_translations: `SELECT id FROM translations WHERE translated_text='' OR engine='' OR model=''`,
    duplicate_evidence: `SELECT min(id::text) AS id FROM evidence_fragments GROUP BY snapshot_id,location,original_text HAVING count(*)>1`,
  };
  const results = [];
  for (const [name, sql] of Object.entries(checks)) {
    const { rows } = await db.query(sql);
    results.push({ name, ok: !rows.length, violations: rows });
  }
  const warnings = (
    await db.query(
      "SELECT id,title,health FROM sources WHERE health IN ('STALE','SUPERSEDED','UNKNOWN')",
    )
  ).rows;
  return {
    ok: results.every((r) => r.ok),
    checked_at: new Date().toISOString(),
    checks: results,
    warnings,
  };
}
