import express, {
  type Request,
  type Response,
  type NextFunction,
} from "express";
import helmet from "helmet";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { z } from "zod";
import type { Database } from "./db.js";
import {
  search,
  searchSchema,
  baseClaimSelect,
  isoDate,
  kinds,
} from "./search.js";
import { auditDatabase } from "./audit.js";
import { publishReviewedClaim } from "./ingestion.js";

const uuid = z.uuid();
const getId = (value: unknown) => uuid.parse(value);
const textQuery = z
  .object({
    q: z.string().max(500).default(""),
    health: z
      .enum([
        "ACTIVE",
        "STALE",
        "DISCONTINUED",
        "ARCHIVED",
        "SUPERSEDED",
        "UNKNOWN",
      ])
      .optional(),
    language: z.string().max(35).optional(),
    publisher: z.string().max(200).optional(),
  })
  .strict();
class HttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export function createApp(
  db: Database,
  {
    reviewToken,
    production = false,
  }: { reviewToken?: string; production?: boolean } = {},
) {
  const app = express();
  app.disable("x-powered-by");
  app.use(
    helmet({
      contentSecurityPolicy: production
        ? {
            directives: {
              defaultSrc: ["'self'"],
              scriptSrc: ["'self'"],
              styleSrc: ["'self'", "'unsafe-inline'"],
              imgSrc: ["'self'", "data:"],
              connectSrc: ["'self'"],
              objectSrc: ["'none'"],
              frameAncestors: ["'none'"],
              baseUri: ["'self'"],
              upgradeInsecureRequests: null,
            },
          }
        : false,
    }),
  );
  app.use(express.json({ limit: "256kb" }));
  app.use((req, res, next) => {
    const requestId = randomUUID(),
      start = Date.now();
    res.setHeader("X-Request-ID", requestId);
    const allowedHosts = new Set([
      "localhost",
      "127.0.0.1",
      "[::1]",
      ...(process.env.PUBLIC_ORIGIN
        ? [new URL(process.env.PUBLIC_ORIGIN).hostname]
        : []),
    ]);
    try {
      if (!allowedHosts.has(new URL(`http://${req.get("host")}`).hostname))
        return res.status(403).json({ error: "Unrecognized host" });
    } catch {
      return res.status(400).json({ error: "Invalid host" });
    }
    // Reject browser cross-origin mutations. Research endpoints require no cross-origin credentials.
    if (
      !["GET", "HEAD", "OPTIONS"].includes(req.method) &&
      req.get("origin") &&
      req.get("origin") !== `${req.protocol}://${req.get("host")}`
    )
      return res.status(403).json({
        error: "Cross-origin mutation rejected",
        request_id: requestId,
      });
    if (req.path.startsWith("/api/"))
      res.on("finish", () =>
        console.log(
          JSON.stringify({
            event: "http_request",
            request_id: requestId,
            method: req.method,
            path: req.path,
            status: res.statusCode,
            duration_ms: Date.now() - start,
          }),
        ),
      );
    next();
  });
  const requireReview = (req: Request, _res: Response, next: NextFunction) => {
    if (!reviewToken)
      return next(
        new HttpError(
          503,
          "Review writes are disabled. Configure REVIEW_TOKEN.",
        ),
      );
    const candidate = Buffer.from(
        req.get("authorization")?.replace(/^Bearer /, "") ?? "",
      ),
      expected = Buffer.from(reviewToken);
    if (
      candidate.length !== expected.length ||
      !timingSafeEqual(candidate, expected)
    )
      return next(new HttpError(401, "Reviewer authorization required."));
    next();
  };
  // Investigations are a single-user workspace locally. Externally exposed deployments must protect all writes.
  const workspaceWrite = (req: Request, res: Response, next: NextFunction) =>
    production ? requireReview(req, res, next) : next();
  app.use("/api/investigations", workspaceWrite);
  app.post("/api/review/claims", requireReview, async (req, res) => {
    res.status(201).json(await publishReviewedClaim(db, req.body));
  });
  app.get("/api/health", async (_req, res) => {
    await db.query("SELECT 1");
    res.json({
      status: "ok",
      product: "HIGH-PROFILE",
      release: "Index 1.0",
      collection: "DEVELOPMENT_REFERENCE_COLLECTION",
    });
  });
  app.get("/api/meta", async (_req, res) => {
    const counts = await db.query(
      `SELECT (SELECT count(*)::int FROM entities) AS entities,(SELECT count(*)::int FROM claims) AS claims,(SELECT count(*)::int FROM sources) AS sources,(SELECT count(*)::int FROM countries) AS countries,(SELECT count(*)::int FROM claim_contradictions WHERE status='OPEN') AS disagreements`,
    );
    res.json({
      counts: counts.rows[0],
      countries: (await db.query("SELECT * FROM countries ORDER BY name")).rows,
      publishers: (
        await db.query("SELECT id,name,tier FROM publishers ORDER BY tier,name")
      ).rows,
      collection: "Development reference collection",
      review_writes: !!reviewToken,
      workspace_writes: !production || !!reviewToken,
    });
  });
  app.get("/api/search", async (req, res) => {
    res.json(await search(db, searchSchema.parse(req.query)));
  });
  app.get("/api/claims", async (req, res) =>
    res.json(await search(db, searchSchema.parse(req.query))),
  );
  app.get("/api/entities", async (req, res) => {
    const f = z
      .object({
        kind: z.enum(kinds).optional(),
        q: z.string().max(200).default(""),
      })
      .strict()
      .parse(req.query);
    res.json({
      items: (
        await db.query(
          `SELECT e.*,co.name AS country_name,(SELECT count(*)::int FROM claims c WHERE c.subject_id=e.id) AS claim_count FROM entities e LEFT JOIN countries co ON co.code=e.country_code WHERE ($1::entity_kind IS NULL OR e.kind=$1::entity_kind) AND (e.name ILIKE $2 OR EXISTS(SELECT 1 FROM aliases a WHERE a.entity_id=e.id AND a.alias ILIKE $2)) ORDER BY e.is_synthetic,e.name`,
          [f.kind ?? null, `%${f.q.replace(/[\\%_]/g, "\\$&")}%`],
        )
      ).rows,
    });
  });
  app.get(
    [
      "/api/entities/:id",
      "/api/countries/:id",
      "/api/facilities/:id",
      "/api/programs/:id",
      "/api/systems/:id",
    ],
    async (req, res) => {
      const key = z.string().max(100).parse(req.params.id);
      const dates = z
        .object({ as_of: isoDate.optional(), known_at: isoDate.optional() })
        .strict()
        .parse(req.query);
      const entity = (
        await db.query(
          `SELECT e.*,co.name AS country_name,co.region FROM entities e LEFT JOIN countries co ON co.code=e.country_code WHERE e.id::text=$1 OR e.slug=$1`,
          [key],
        )
      ).rows[0];
      if (!entity) throw new HttpError(404, "Profile not found.");
      const result = await search(
        db,
        searchSchema.parse({ ...dates, limit: 100 }),
        entity.id,
      );
      const claims = result.items.filter((x) => x.subject_id === entity.id);
      const relationships = (
        await db.query(
          `SELECT r.*,s.name AS subject_name,s.slug AS subject_slug,o.name AS object_name,o.slug AS object_slug FROM relationships r JOIN entities s ON s.id=r.subject_id JOIN entities o ON o.id=r.object_id WHERE r.subject_id=$1 OR r.object_id=$1`,
          [entity.id],
        )
      ).rows;
      const visibleClaimIds = new Set(
        (
          await db.query(
            `SELECT DISTINCT claim_id FROM claim_versions WHERE published AND public_on<=$1::date AND effective_from<=$1::date AND recorded_at<($2::date+interval '1 day')`,
            [dates.as_of ?? "9999-12-31", dates.known_at ?? "9999-12-31"],
          )
        ).rows.map((c) => c.claim_id),
      );
      res.json({
        ...entity,
        aliases: (
          await db.query(
            "SELECT alias,language FROM aliases WHERE entity_id=$1",
            [entity.id],
          )
        ).rows,
        claims,
        relationships: relationships.filter(
          (r) => !r.claim_id || visibleClaimIds.has(r.claim_id),
        ),
        temporal_mode: result.temporal_mode,
      });
    },
  );
  for (const [path, types] of Object.entries({
    countries: ["COUNTRY"],
    facilities: ["FACILITY", "REACTOR"],
    programs: ["PROGRAM"],
    systems: ["WEAPON_SYSTEM", "DELIVERY_SYSTEM"],
  }))
    app.get(`/api/${path}`, async (_req, res) =>
      res.json({
        items: (
          await db.query(
            "SELECT * FROM entities WHERE kind::text=ANY($1::text[]) ORDER BY name",
            [types],
          )
        ).rows,
      }),
    );
  app.get("/api/claims/:id", async (req, res) => {
    const key = getId(req.params.id);
    const filter = z
      .object({
        version: z.coerce.number().int().positive().optional(),
        as_of: isoDate.optional(),
        known_at: isoDate.optional(),
      })
      .strict()
      .parse(req.query);
    const versions = (
      await db.query(
        `${baseClaimSelect} WHERE v.claim_id=$1 AND v.published AND v.public_on<=$2::date AND v.effective_from<=$2::date AND v.recorded_at<($3::date+interval '1 day') ORDER BY v.version DESC`,
        [key, filter.as_of ?? "9999-12-31", filter.known_at ?? "9999-12-31"],
      )
    ).rows;
    const current = filter.version
      ? versions.find((v) => v.version === filter.version)
      : versions[0];
    if (!current)
      throw new HttpError(404, "No published claim version for this date.");
    const evidence = (
      await db.query(
        `SELECT ef.*,ce.role,ce.note,ss.retrieved_at,ss.content_hash,ss.hash_scope,ss.method,ss.retrieval_note,s.id AS source_id,s.title,s.canonical_url,s.published_on,s.health,s.license,s.is_synthetic AS synthetic_source,p.name AS publisher,p.tier,p.independence_group,p.notes AS publisher_notes,COALESCE((SELECT jsonb_agg(t) FROM translations t WHERE t.evidence_id=ef.id),'[]'::jsonb) AS translations FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ce.version_id=$1 ORDER BY ce.role DESC,s.published_on DESC`,
        [current.id],
      )
    ).rows;
    const contradictions = (
      await db.query(
        `SELECT cc.*,other.claim_id AS other_claim_id,other.statement AS other_statement FROM claim_contradictions cc JOIN claim_versions other ON other.id=CASE WHEN cc.left_version_id=$1 THEN cc.right_version_id ELSE cc.left_version_id END WHERE (cc.left_version_id=$1 OR cc.right_version_id=$1) AND other.public_on<=$2::date AND other.recorded_at<($3::date+interval '1 day')`,
        [
          current.id,
          filter.as_of ?? "9999-12-31",
          filter.known_at ?? "9999-12-31",
        ],
      )
    ).rows;
    res.json({ ...current, evidence, versions, contradictions });
  });
  app.get("/api/sources", async (req, res) => {
    const f = textQuery.parse(req.query);
    const args = [
      `%${f.q.replace(/[\\%_]/g, "\\$&")}%`,
      f.health ?? null,
      f.language ?? null,
      f.publisher ?? null,
    ];
    res.json({
      items: (
        await db.query(
          `SELECT s.*,p.name AS publisher,p.tier,(SELECT max(retrieved_at) FROM source_snapshots WHERE source_id=s.id) AS retrieved_at,(SELECT count(DISTINCT ce.version_id)::int FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id WHERE ss.source_id=s.id AND ce.role='SUPPORTS') AS claims_supported,(SELECT count(DISTINCT ce.version_id)::int FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id WHERE ss.source_id=s.id AND ce.role='CONTRADICTS') AS claims_contradicted FROM sources s JOIN publishers p ON p.id=s.publisher_id WHERE (s.title ILIKE $1 OR p.name ILIKE $1) AND ($2::source_health IS NULL OR s.health=$2::source_health) AND ($3::text IS NULL OR s.language=$3) AND ($4::text IS NULL OR p.name=$4) ORDER BY s.is_synthetic,s.published_on DESC`,
          args,
        )
      ).rows,
    });
  });
  app.get("/api/sources/:id", async (req, res) => {
    const source = (
      await db.query(
        "SELECT s.*,p.name AS publisher,p.tier,p.notes AS publisher_notes FROM sources s JOIN publishers p ON p.id=s.publisher_id WHERE s.id=$1",
        [getId(req.params.id)],
      )
    ).rows[0];
    if (!source) throw new HttpError(404, "Source not found.");
    res.json({
      ...source,
      snapshots: (
        await db.query(
          "SELECT * FROM source_snapshots WHERE source_id=$1 ORDER BY retrieved_at DESC",
          [source.id],
        )
      ).rows,
      claims: (
        await db.query(
          `${baseClaimSelect} WHERE v.published AND EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id WHERE ce.version_id=v.id AND ss.source_id=$1) ORDER BY v.public_on DESC,e.name`,
          [source.id],
        )
      ).rows,
    });
  });
  app.get("/api/timeline", async (req, res) => {
    const f = z
      .object({ entity: z.uuid().optional() })
      .strict()
      .parse(req.query);
    res.json({
      items: (
        await db.query(
          `${baseClaimSelect} WHERE v.published AND ($1::uuid IS NULL OR c.subject_id=$1::uuid) ORDER BY v.public_on DESC,v.version DESC`,
          [f.entity ?? null],
        )
      ).rows,
    });
  });
  app.get("/api/watch", async (_req, res) =>
    res.json({
      mode: "RECORD_CHANGE_LOG",
      automated_monitoring: false,
      items: (
        await db.query(
          "SELECT w.*,e.name AS entity_name,e.slug AS entity_slug,v.claim_id,v.version,v.public_on,v.effective_from FROM watch_events w LEFT JOIN entities e ON e.id=w.entity_id LEFT JOIN claim_versions v ON v.id=w.version_id ORDER BY w.occurred_at DESC,w.id",
        )
      ).rows,
    }),
  );
  app.get("/api/integrity", async (_req, res) =>
    res.json(await auditDatabase(db)),
  );
  app.get("/api/investigations", async (_req, res) =>
    res.json({
      items: (
        await db.query(
          "SELECT i.*,(SELECT count(*)::int FROM investigation_items WHERE investigation_id=i.id) AS item_count FROM investigations i ORDER BY i.updated_at DESC",
        )
      ).rows,
    }),
  );
  app.post("/api/investigations", workspaceWrite, async (req, res) => {
    const b = z
      .object({
        title: z.string().trim().min(1).max(200),
        description: z.string().max(4000).default(""),
      })
      .strict()
      .parse(req.body);
    const item = (
      await db.query(
        "INSERT INTO investigations(id,title,description) VALUES($1,$2,$3) RETURNING *",
        [randomUUID(), b.title, b.description],
      )
    ).rows[0];
    res.status(201).json(item);
  });
  app.get("/api/investigations/:id", async (req, res) => {
    const key = getId(req.params.id);
    const inv = (
      await db.query("SELECT * FROM investigations WHERE id=$1", [key])
    ).rows[0];
    if (!inv) throw new HttpError(404, "Investigation not found.");
    const items = (
      await db.query(
        `SELECT i.*,v.statement,v.claim_id,v.version,v.classification,v.confidence,v.public_on,v.effective_from,e.name AS entity_name,e.slug AS entity_slug FROM investigation_items i LEFT JOIN claim_versions v ON v.id=i.version_id LEFT JOIN claims c ON c.id=v.claim_id LEFT JOIN entities e ON e.id=c.subject_id WHERE i.investigation_id=$1 ORDER BY i.created_at DESC`,
        [key],
      )
    ).rows;
    res.json({ ...inv, items });
  });
  app.post(
    "/api/investigations/:id/items",
    workspaceWrite,
    async (req, res) => {
      const key = getId(req.params.id),
        b = z
          .object({
            version_id: z.uuid(),
            note: z.string().max(8000).default(""),
          })
          .strict()
          .parse(req.body);
      if (
        !(await db.query("SELECT id FROM investigations WHERE id=$1", [key]))
          .rows.length
      )
        throw new HttpError(404, "Investigation not found.");
      if (
        !(
          await db.query(
            "SELECT id FROM claim_versions WHERE id=$1 AND published",
            [b.version_id],
          )
        ).rows.length
      )
        throw new HttpError(404, "Published version not found.");
      await db.transaction(async (tx) => {
        await tx.query(
          "INSERT INTO investigation_items(id,investigation_id,version_id,note) VALUES($1,$2,$3,$4) ON CONFLICT(investigation_id,version_id) DO UPDATE SET note=EXCLUDED.note",
          [randomUUID(), key, b.version_id, b.note],
        );
        await tx.query(
          "UPDATE investigations SET updated_at=now() WHERE id=$1",
          [key],
        );
      });
      res.status(201).json({ saved: true });
    },
  );
  app.get("/api/investigations/:id/export", async (req, res) => {
    const key = getId(req.params.id),
      inv = (await db.query("SELECT * FROM investigations WHERE id=$1", [key]))
        .rows[0];
    if (!inv) throw new HttpError(404, "Investigation not found.");
    const items = (
      await db.query(
        `${baseClaimSelect.replace("SELECT v.*,", "SELECT v.*,i.note,")} JOIN investigation_items i ON i.version_id=v.id WHERE i.investigation_id=$1 ORDER BY e.name,v.public_on`,
        [key],
      )
    ).rows;
    const plain = (x: unknown) =>
      String(x)
        .replace(/[<>]/g, "")
        .replace(/([\\\[\]`*_#])/g, "\\$1");
    const report = [
      `# ${plain(inv.title)}`,
      plain(inv.description),
      "HIGH-PROFILE · Development reference collection. Selective historical evidence, not a current global assessment.",
      `Exported ${new Date().toISOString()}`,
      ...items.flatMap((v) => [
        `## ${plain(v.entity_name)}`,
        plain(v.statement),
        `${v.classification} · ${v.confidence} confidence · effective ${String(v.effective_from).slice(0, 10)} · public ${String(v.public_on).slice(0, 10)}`,
        `Pinned version ${v.version} · ${v.id}`,
        `Research note: ${plain(v.note)}`,
        `Confidence rationale: ${plain(JSON.stringify(v.confidence_rationale))}`,
        ...v.provenance.map(
          (s: any) =>
            `- ${s.role}: ${plain(s.publisher)}. ${plain(s.title)}. ${s.published_on}. ${s.url} (retrieved ${s.retrieved_at}; ${s.health})`,
        ),
      ]),
      "Scope: This export is a cited collection of pinned claims; it is not an independently authored assessment.",
    ].join("\n\n");
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="high-profile-investigation-${key}.md"`,
    );
    res.type("text/markdown").send(report);
  });
  app.use("/api", (_req, _res, next) =>
    next(new HttpError(404, "API route not found.")),
  );
  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    const status = err instanceof z.ZodError ? 400 : (err.status ?? 500);
    console.error(
      JSON.stringify({ event: "api_error", status, message: err.message }),
    );
    res.status(status).json({
      error:
        status === 500
          ? "The request could not be completed. See server logs."
          : err instanceof z.ZodError
            ? "Invalid request parameters"
            : err.message,
      details:
        err instanceof z.ZodError
          ? err.issues.map((i) => ({ path: i.path, message: i.message }))
          : undefined,
    });
  });
  return app;
}
