import { z } from "zod";
import { isIP } from "node:net";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import type { Database } from "./db.js";
import { isoDate, classes, confidences } from "./search.js";

export function safePublicUrl(raw: string) {
  const url = new URL(raw);
  const host = url.hostname.toLowerCase();
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    (url.port && url.port !== "443") ||
    host === "localhost" ||
    !host.includes(".") ||
    isIP(host) ||
    host.startsWith("[") ||
    /\.(local|internal|localhost|test|invalid)$/.test(host) ||
    /^\d+(\.\d+)*$/.test(host)
  )
    throw new Error(
      "Only public HTTPS source URLs without credentials are accepted",
    );
  return url.href;
}
const language = z.string().regex(/^[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*$/);
export const documentSchema = z
  .object({
    title: z.string().trim().min(1).max(500),
    url: z.string().max(2000).transform(safePublicUrl),
    publisher_id: z.uuid(),
    published_on: isoDate,
    language,
    document_type: z.string().min(1).max(100),
    dataset_version: z.string().min(1).max(100),
    license: z.string().min(1).max(2000),
    text: z.string().min(1).max(150000),
    location: z.string().min(1).max(500),
    is_synthetic: z.boolean().default(false),
  })
  .strict();
export type SourceDocument = z.infer<typeof documentSchema>;
export interface DiscoveryCandidate {
  url: string;
  title: string;
  publisher?: string;
  language?: string;
  provider: string;
}
export interface DiscoveryProvider {
  readonly name: string;
  discover(
    query: string,
    signal?: AbortSignal,
  ): AsyncIterable<DiscoveryCandidate>;
}
export interface DocumentProvider {
  readonly name: string;
  documents(): AsyncIterable<SourceDocument>;
}
export class ManualSourceProvider implements DocumentProvider {
  readonly name = "manual";
  constructor(private readonly records: unknown[]) {}
  async *documents() {
    for (const record of this.records) yield documentSchema.parse(record);
  }
}
export class TractorProvider implements DiscoveryProvider {
  readonly name = "tractor";
  constructor(
    private readonly searchClient: (
      q: string,
      signal?: AbortSignal,
    ) => Promise<{ url: string; title: string }[]>,
  ) {}
  async *discover(query: string, signal?: AbortSignal) {
    for (const result of await this.searchClient(query, signal)) {
      yield {
        url: safePublicUrl(result.url),
        title: z.string().max(500).parse(result.title),
        provider: this.name,
      };
    }
  }
}
export interface DocumentStore {
  put(content: string): Promise<string>;
  get(key: string): Promise<string>;
}
export class LocalDocumentStore implements DocumentStore {
  constructor(private readonly directory: string) {}
  async put(content: string) {
    const key = createHash("sha256").update(content).digest("hex");
    await mkdir(this.directory, { recursive: true });
    await writeFile(join(this.directory, key + ".txt"), content, {
      mode: 0o600,
    });
    return key;
  }
  async get(key: string) {
    if (!/^[a-f0-9]{64}$/.test(key)) throw new Error("Invalid storage key");
    return readFile(join(this.directory, key + ".txt"), "utf8");
  }
}
export async function resolveEntity(db: Database, text: string) {
  const normalized = text.normalize("NFKC").trim().toLowerCase();
  const matches = (
    await db.query(
      "SELECT DISTINCT e.id,e.name,e.slug FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id WHERE lower(e.name)=$1 OR a.normalized=$1",
      [normalized],
    )
  ).rows;
  return {
    status:
      matches.length === 1
        ? "RESOLVED"
        : matches.length > 1
          ? "AMBIGUOUS"
          : "UNRESOLVED",
    matches,
  };
}
/** No fetching, instructions, LLM calls or auto-publication. The input is untrusted data. */
export async function ingestDocument(
  db: Database,
  raw: unknown,
  store: DocumentStore,
) {
  const jobId = randomUUID();
  await db.query(
    "INSERT INTO ingestion_jobs(id,provider,status,attempts,started_at) VALUES($1,'manual','RUNNING',1,now())",
    [jobId],
  );
  try {
    const doc = documentSchema.parse(raw);
    if (doc.published_on > new Date().toISOString().slice(0, 10))
      throw new Error("Future publication date");
    const storageKey = await store.put(doc.text),
      sourceId = randomUUID(),
      snapshotId = randomUUID(),
      evidenceId = randomUUID(),
      now = new Date().toISOString();
    await db.transaction(async (tx) => {
      await tx.query(
        `INSERT INTO sources(id,publisher_id,title,canonical_url,published_on,language,document_type,dataset_version,health,archival_status,license,is_synthetic) VALUES($1,$2,$3,$4,$5,$6,$7,$8,'UNKNOWN','Locally retained authorized text',$9,$10)`,
        [
          sourceId,
          doc.publisher_id,
          doc.title,
          doc.url,
          doc.published_on,
          doc.language,
          doc.document_type,
          doc.dataset_version,
          doc.license,
          doc.is_synthetic,
        ],
      );
      await tx.query(
        `INSERT INTO source_snapshots(id,source_id,retrieved_at,content_hash,hash_scope,method,storage_key,retrieval_note) VALUES($1,$2,$3,$4,'Exact submitted UTF-8 text','manual-submission',$4,'Submitted by a researcher; no network retrieval asserted.')`,
        [snapshotId, sourceId, now, storageKey],
      );
      await tx.query(
        `INSERT INTO evidence_fragments(id,snapshot_id,original_text,language,normalized_extraction,location,extraction_method,extracted_at) VALUES($1,$2,$3,$4,$3,$5,'manual-text',$6)`,
        [evidenceId, snapshotId, doc.text, doc.language, doc.location, now],
      );
      await tx.query(
        "UPDATE ingestion_jobs SET status='REVIEW',source_id=$2,finished_at=now() WHERE id=$1",
        [jobId, sourceId],
      );
      await tx.query(
        "INSERT INTO audit_logs(id,action,record_id,detail) VALUES($1,'DOCUMENT_INGESTED',$2,$3)",
        [
          randomUUID(),
          sourceId,
          JSON.stringify({ job_id: jobId, review_required: true }),
        ],
      );
    });
    return {
      job_id: jobId,
      source_id: sourceId,
      evidence_id: evidenceId,
      status: "REVIEW",
    };
  } catch (error) {
    await db.query(
      "UPDATE ingestion_jobs SET status='FAILED',error=$2,finished_at=now() WHERE id=$1",
      [jobId, String((error as Error).message).slice(0, 2000)],
    );
    throw error;
  }
}
export const reviewSchema = z
  .object({
    subject_id: z.uuid(),
    claim_id: z.uuid().optional(),
    predicate: z.string().min(1).max(100),
    statement: z.string().min(1).max(4000),
    value: z.record(z.string(), z.unknown()),
    classification: z.enum(classes),
    confidence: z.enum(confidences),
    confidence_rationale: z
      .object({
        authority: z.string().min(1),
        independence: z.string().min(1),
        directness: z.string().min(1),
        recency: z.string().min(1),
        limitations: z.string().min(1),
      })
      .strict(),
    effective_from: isoDate,
    public_on: isoDate,
    evidence: z
      .array(
        z.object({
          id: z.uuid(),
          role: z.enum(["SUPPORTS", "CONTRADICTS", "CONTEXT"]),
        }),
      )
      .min(1)
      .max(30),
    notes: z.string().min(1).max(8000),
    is_synthetic: z.boolean().default(false),
  })
  .strict();
export async function publishReviewedClaim(db: Database, input: unknown) {
  const candidate = reviewSchema.parse(input),
    versionId = randomUUID();
  return db.transaction(async (tx) => {
    const claimId = candidate.claim_id ?? randomUUID();
    let prev: any;
    if (candidate.claim_id) {
      const claim = (
        await tx.query("SELECT * FROM claims WHERE id=$1 FOR UPDATE", [claimId])
      ).rows[0];
      if (
        !claim ||
        claim.subject_id !== candidate.subject_id ||
        claim.predicate !== candidate.predicate
      )
        throw new Error("Claim identity mismatch");
      prev = (
        await tx.query(
          "SELECT * FROM claim_versions WHERE claim_id=$1 ORDER BY version DESC LIMIT 1",
          [claimId],
        )
      ).rows[0];
    } else
      await tx.query(
        "INSERT INTO claims(id,subject_id,predicate) VALUES($1,$2,$3)",
        [claimId, candidate.subject_id, candidate.predicate],
      );
    const now = new Date().toISOString();
    await tx.query(
      `INSERT INTO claim_versions(id,claim_id,version,statement,value,classification,confidence,confidence_rationale,effective_from,public_on,recorded_at,reviewed_at,supersedes_id,notes,is_synthetic) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11,$12,$13,$14)`,
      [
        versionId,
        claimId,
        (prev?.version ?? 0) + 1,
        candidate.statement,
        JSON.stringify(candidate.value),
        candidate.classification,
        candidate.confidence,
        JSON.stringify(candidate.confidence_rationale),
        candidate.effective_from,
        candidate.public_on,
        now,
        prev?.id ?? null,
        candidate.notes,
        candidate.is_synthetic,
      ],
    );
    for (const e of candidate.evidence)
      await tx.query(
        "INSERT INTO claim_evidence(version_id,evidence_id,role,note) VALUES($1,$2,$3,$4)",
        [versionId, e.id, e.role, "Reviewer-selected evidence."],
      );
    await tx.query("UPDATE claim_versions SET published=true WHERE id=$1", [
      versionId,
    ]);
    await tx.query(
      "INSERT INTO audit_logs(id,action,record_id,detail) VALUES($1,'CLAIM_PUBLISHED',$2,$3)",
      [
        randomUUID(),
        versionId,
        JSON.stringify({
          actor: "authorized-reviewer",
          version: (prev?.version ?? 0) + 1,
        }),
      ],
    );
    await tx.query(
      "INSERT INTO watch_events(id,entity_id,version_id,type,description,occurred_at,is_synthetic) VALUES($1,$2,$3,$4,$5,$6,$7)",
      [
        randomUUID(),
        candidate.subject_id,
        versionId,
        prev ? "ASSESSMENT_REVISED" : "CLAIM_ADDED",
        candidate.statement,
        now,
        candidate.is_synthetic,
      ],
    );
    return {
      claim_id: claimId,
      version_id: versionId,
      version: (prev?.version ?? 0) + 1,
    };
  });
}
