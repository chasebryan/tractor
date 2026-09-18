import { z } from "zod";
import type { Database } from "./db.js";
export const classes = [
  "DOCUMENTED",
  "OFFICIALLY_STATED",
  "ASSESSED",
  "ESTIMATED",
  "REPORTED",
  "DISPUTED",
  "UNVERIFIED",
  "HISTORICAL",
  "SUPERSEDED",
  "RETRACTED",
] as const;
export const confidences = [
  "VERY HIGH",
  "HIGH",
  "MODERATE",
  "LOW",
  "INSUFFICIENT",
] as const;
export const kinds = [
  "COUNTRY",
  "ORGANIZATION",
  "PROGRAM",
  "FACILITY",
  "WEAPON_SYSTEM",
  "DELIVERY_SYSTEM",
  "REACTOR",
  "FUEL_CYCLE_CAPABILITY",
  "TREATY",
  "AGREEMENT",
  "EVENT",
] as const;
export const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine(
    (v) =>
      !Number.isNaN(Date.parse(v)) &&
      new Date(v).toISOString().slice(0, 10) === v,
    "Invalid calendar date",
  );
export const searchSchema = z
  .object({
    q: z.string().max(500).default(""),
    country: z
      .string()
      .regex(/^[A-Z]{2}$/)
      .optional(),
    kind: z.enum(kinds).optional(),
    classification: z.enum(classes).optional(),
    confidence: z.enum(confidences).optional(),
    as_of: isoDate.optional(),
    known_at: isoDate.optional(),
    since: isoDate.optional(),
    until: isoDate.optional(),
    publisher: z.string().max(200).optional(),
    source: z.uuid().optional(),
    region: z.string().max(100).optional(),
    min_evidence: z.coerce.number().int().min(0).max(100).optional(),
    disputed: z.enum(["true", "false"]).optional(),
    changed: z.enum(["true", "false"]).optional(),
    synthetic: z.enum(["true", "false"]).optional(),
    page: z.coerce.number().int().min(1).max(10000).default(1),
    limit: z.coerce.number().int().min(1).max(100).default(30),
  })
  .strict();
export type SearchInput = z.infer<typeof searchSchema>;
export function interpretQuery(raw: SearchInput) {
  const filters = { ...raw };
  let text = raw.q.trim();
  const interpretation: string[] = [];
  const countryMap: Record<string, string> = {
    china: "CN",
    chinese: "CN",
    france: "FR",
    french: "FR",
    russia: "RU",
    russian: "RU",
    "united kingdom": "GB",
    "united states": "US",
    "united arab emirates": "AE",
    uae: "AE",
  };
  // Interpret only a bounded grammar. Arbitrary questions are retained as keywords, never sent to a model.
  const natural = /^(show|find|which|list)\b/i.test(text);
  if (natural) {
    for (const [word, code] of Object.entries(countryMap)) {
      const re = new RegExp(`\\b${word}(?:['’]s)?\\b`, "ig");
      if (re.test(text)) {
        if (!filters.country) filters.country = code;
        text = text.replace(re, " ");
        break;
      }
    }
    const since = text.match(/\bsince (\d{4})(?:-(\d{2})-(\d{2}))?\b/i);
    if (since) {
      filters.since =
        filters.since ?? `${since[1]}-${since[2] ?? "01"}-${since[3] ?? "01"}`;
      isoDate.parse(filters.since);
      text = text.replace(since[0], " ");
    }
    if (/\bdocumented\b/i.test(text)) {
      filters.classification ??= "DOCUMENTED";
      text = text.replace(/\bdocumented\b/gi, " ");
    }
    if (/\b(disagreements|contradictions|disputed)\b/i.test(text)) {
      filters.disputed = "true";
      text = text.replace(/\b(disagreements|contradictions|disputed)\b/gi, " ");
    }
    if (/\b(changed|changes|revised)\b/i.test(text)) {
      filters.changed = "true";
      text = text.replace(/\b(changed|changes|revised)\b/gi, " ");
    }
    text = text
      .replace(
        /\b(show|find|which|list|to|the|of|in|public|evidence|capabilities|assessments|nuclear|programmes|programs|have|has|countries|country|all|about)\b/gi,
        " ",
      )
      .replace(/[?.!,;:]+$/g, "")
      .replace(/\s+/g, " ")
      .trim();
    interpretation.push(
      "Bounded query interpretation; review the filters and remaining keywords.",
    );
  }
  filters.q = text;
  for (const [key, value] of Object.entries(filters))
    if (!["page", "limit"].includes(key) && value !== undefined && value !== "")
      interpretation.push(`${key}: ${value}`);
  return {
    filters,
    interpretation,
    natural_language: natural,
    notice: natural
      ? "Only countries, “since”, documented, disagreements and changes are interpreted. Other words remain literal search terms."
      : null,
  };
}
export const provenanceSql = `COALESCE((SELECT jsonb_agg(jsonb_build_object('id',s.id,'title',s.title,'publisher',p.name,'tier',p.tier,'health',s.health,'published_on',s.published_on,'url',s.canonical_url,'role',ce.role,'retrieved_at',ss.retrieved_at,'snapshot_id',ss.id)) FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ce.version_id=v.id),'[]'::jsonb)`;
export const claimSelect = `SELECT v.*,c.subject_id,c.predicate,c.first_observed,e.name AS entity_name,e.slug AS entity_slug,e.kind,e.country_code,${provenanceSql} AS provenance,
 (SELECT count(*)::int FROM claim_evidence WHERE version_id=v.id AND role='SUPPORTS') AS evidence_count,
 (SELECT count(*)::int FROM claim_evidence WHERE version_id=v.id AND role='CONTRADICTS') AS contrary_count,
 (SELECT count(DISTINCT p.independence_group)::int FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ce.version_id=v.id AND ce.role='SUPPORTS') AS independent_groups
 FROM claims c JOIN entities e ON e.id=c.subject_id JOIN countries country ON country.code=e.country_code RIGHT JOIN claim_versions v ON v.claim_id=c.id`;
// LEFT country join is required for global treaties and synthetic programmes.
export const baseClaimSelect = claimSelect
  .replace("JOIN countries country", "LEFT JOIN countries country")
  .replace("RIGHT JOIN claim_versions", "JOIN claim_versions");
export async function search(
  db: Database,
  input: SearchInput,
  subjectId?: string,
) {
  const interpreted = interpretQuery(input),
    f = interpreted.filters;
  const args: unknown[] = [];
  const param = (value: unknown) => {
    args.push(value);
    return `$${args.length}`;
  };
  const date = param(f.as_of ?? "9999-12-31"),
    known = param(f.known_at ?? "9999-12-31");
  const latest = `v.published AND v.id=(SELECT x.id FROM claim_versions x WHERE x.claim_id=c.id AND x.published AND x.public_on<=${date}::date AND x.effective_from<=${date}::date AND x.recorded_at<(${known}::date+interval '1 day') ORDER BY x.version DESC LIMIT 1)`;
  const where = [latest];
  if (subjectId) where.push(`c.subject_id=${param(subjectId)}::uuid`);
  if (f.q) {
    const ts = param(f.q),
      like = param(`%${f.q.replace(/[\\%_]/g, "\\$&")}%`);
    const text = `e.name||' '||e.description||' '||v.statement||' '||coalesce((SELECT string_agg(alias,' ') FROM aliases WHERE entity_id=e.id),'')||' '||coalesce((SELECT name FROM countries WHERE code=e.country_code),'')`;
    where.push(
      `(to_tsvector('simple',${text}) @@ plainto_tsquery('simple',${ts}) OR to_tsvector('english',${text}) @@ plainto_tsquery('english',${ts}) OR e.name ILIKE ${like} OR v.statement ILIKE ${like} OR EXISTS(SELECT 1 FROM aliases a WHERE a.entity_id=e.id AND a.alias ILIKE ${like}))`,
    );
  }
  if (f.country) where.push(`e.country_code=${param(f.country)}`);
  if (f.kind) where.push(`e.kind=${param(f.kind)}::entity_kind`);
  if (f.classification)
    where.push(`v.classification=${param(f.classification)}::claim_class`);
  if (f.confidence)
    where.push(`v.confidence=${param(f.confidence)}::confidence_level`);
  if (f.region) where.push(`country.region=${param(f.region)}`);
  if (f.since) where.push(`v.public_on>=${param(f.since)}::date`);
  if (f.until) where.push(`v.public_on<=${param(f.until)}::date`);
  if (f.synthetic === "false") where.push("NOT v.is_synthetic");
  if (f.changed === "true") where.push("v.version>1");
  if (f.disputed === "true")
    where.push(
      `EXISTS(SELECT 1 FROM claim_evidence ce WHERE ce.version_id=v.id AND ce.role='CONTRADICTS')`,
    );
  if (f.min_evidence)
    where.push(
      `(SELECT count(*) FROM claim_evidence ce WHERE ce.version_id=v.id AND ce.role='SUPPORTS')>=${param(f.min_evidence)}`,
    );
  if (f.source || f.publisher) {
    const terms = ["ce.version_id=v.id"];
    if (f.source) terms.push(`s.id=${param(f.source)}::uuid`);
    if (f.publisher) terms.push(`p.name=${param(f.publisher)}`);
    where.push(
      `EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ${terms.join(" AND ")})`,
    );
  }
  const query = `${baseClaimSelect} WHERE ${where.join(" AND ")}`;
  const count = await db.query(
    `SELECT count(*)::int AS count FROM (${query}) r`,
    args,
  );
  const rows = await db.query(
    `${query} ORDER BY v.is_synthetic,v.public_on DESC,e.name,v.id LIMIT ${param(f.limit)} OFFSET ${param((f.page - 1) * f.limit)}`,
    args,
  );
  return {
    items: rows.rows,
    total: count.rows[0].count,
    page: f.page,
    limit: f.limit,
    interpreted,
    collection: "DEVELOPMENT_REFERENCE_COLLECTION",
    temporal_mode: f.known_at
      ? "System knowledge cutoff plus publication cutoff"
      : "Reconstruction by public availability; not a claim of historical system knowledge",
  };
}
