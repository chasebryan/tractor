import { createHash } from "node:crypto";
import type { Database } from "./db.js";
export function id(key: string) {
  const h = createHash("sha256").update(`high-profile:${key}`).digest("hex");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-a${h.slice(17, 20)}-${h.slice(20, 32)}`;
}
export const seedSources = {
  sipri25: "https://www.sipri.org/yearbook/2025/06",
  sipri24: "https://www.sipri.org/yearbook/2024/07",
  enec: "https://www.enec.ae/news/latest-news/uae-celebrates-historic-milestone-as-unit-4-of-the-barakah-plant-commences-commercial-operation/",
  france:
    "https://www.elysee.fr/emmanuel-macron/2020/02/07/discours-du-president-emmanuel-macron-sur-la-strategie-de-defense-et-de-dissuasion-devant-les-stagiaires-de-la-27eme-promotion-de-lecole-de-guerre",
  npt: "https://treaties.un.org/Pages/showDetails.aspx?objid=08000002801d56c5",
};
export async function seedDatabase(db: Database) {
  if ((await db.query("SELECT id FROM entities LIMIT 1")).rows.length) return;
  await db.transaction(async (tx) => {
    const now = new Date().toISOString();
    const put = async (table: string, data: Record<string, unknown>) => {
      const cols = Object.keys(data);
      await tx.query(
        `INSERT INTO ${table} (${cols.join(",")}) VALUES (${cols.map((_, i) => `$${i + 1}`).join(",")})`,
        Object.values(data).map((v) =>
          typeof v === "object" && v !== null ? JSON.stringify(v) : v,
        ),
      );
    };
    const countries = [
      ["CN", "China", "East Asia"],
      ["FR", "France", "Europe"],
      ["GB", "United Kingdom", "Europe"],
      ["AE", "United Arab Emirates", "Western Asia"],
      ["US", "United States", "North America"],
      ["RU", "Russia", "Europe / Northern Asia"],
    ];
    for (const [code, name, region] of countries) {
      await put("countries", { code, name, region });
      await put("entities", {
        id: id(code),
        slug: name.toLowerCase().replaceAll(" ", "-"),
        kind: "COUNTRY",
        name,
        country_code: code,
        description: `Public-source country dossier. This development collection is selective and historically bounded; absence of a claim does not establish absence of a capability.`,
        broad_location: region,
      });
    }
    const entities = [
      [
        "china-program",
        "PROGRAM",
        "Chinese nuclear forces",
        "CN",
        "Strategic forces research collection. Stockpile estimates are attributed to their source and effective date.",
        "China",
      ],
      [
        "france-program",
        "PROGRAM",
        "French nuclear deterrence",
        "FR",
        "Historical doctrine and capability statements. This dossier does not represent a current force assessment.",
        "France",
      ],
      [
        "barakah",
        "FACILITY",
        "Barakah Nuclear Energy Plant",
        "AE",
        "Civilian nuclear power facility. The evidence collection covers the announcement of full-fleet commercial operation.",
        "Abu Dhabi Emirate",
      ],
      [
        "barakah-4",
        "REACTOR",
        "Barakah Unit 4",
        "AE",
        "Civilian reactor unit. Operating milestones are represented as dated claims.",
        "Abu Dhabi Emirate",
      ],
      [
        "enec",
        "ORGANIZATION",
        "Emirates Nuclear Energy Corporation",
        "AE",
        "Organization named in the 2024 Barakah source publication.",
        "United Arab Emirates",
      ],
      [
        "airborne",
        "DELIVERY_SYSTEM",
        "French airborne nuclear component",
        "FR",
        "Delivery-system category, recorded from a 2020 doctrine statement. No armament is inferred from platform capability.",
        "France",
      ],
      [
        "npt",
        "TREATY",
        "Treaty on the Non-Proliferation of Nuclear Weapons",
        null,
        "Treaty reference and entry-into-force record.",
        "Global",
      ],
      [
        "review-scenario",
        "PROGRAM",
        "Illustrative fuel-cycle programme",
        null,
        "SYNTHETIC TEST CASE. Two fictional reports disagree about a fictional programme. These records demonstrate review workflows and are not real intelligence.",
        "Not applicable",
      ],
    ];
    for (const [
      key,
      kind,
      name,
      country_code,
      description,
      broad_location,
    ] of entities) {
      await put("entities", {
        id: id(key!),
        slug: key,
        kind,
        name,
        country_code,
        description,
        broad_location,
        is_synthetic: key === "review-scenario",
        sensitivity: ["airborne", "france-program", "china-program"].includes(
          key!,
        )
          ? "GENERALIZED"
          : "PUBLIC",
      });
    }
    for (const [key, alias, language] of [
      ["CN", "中国", "zh"],
      ["CN", "PRC", "en"],
      ["GB", "UK", "en"],
      ["US", "USA", "en"],
      ["AE", "UAE", "en"],
      ["npt", "NPT", "en"],
      ["france-program", "Dissuasion nucléaire", "fr"],
      ["barakah", "براكة", "ar"],
      ["airborne", "aircraft delivery", "en"],
    ])
      await put("aliases", {
        id: id(`alias:${alias}`),
        entity_id: id(key),
        alias,
        language,
        normalized: alias.normalize("NFKC").toLowerCase(),
      });
    const publishers = [
      [
        "sipri",
        "SIPRI",
        2,
        "sipri-nuclear-notebook",
        "https://www.sipri.org",
        "Research institute. Shared authorship with Nuclear Notebook must not be counted as independent corroboration.",
      ],
      [
        "enec",
        "ENEC",
        1,
        "uae-enec",
        "https://www.enec.ae",
        "Official operator-associated publication; authoritative on its announcements, not independent verification.",
      ],
      [
        "elysee",
        "Présidence de la République",
        1,
        "fr-government",
        "https://www.elysee.fr",
        "Official statements establish what was said, not independent verification of every underlying claim.",
      ],
      [
        "un",
        "United Nations Treaty Collection",
        1,
        "un",
        "https://treaties.un.org",
        "Depositary and treaty-registration records.",
      ],
      [
        "fixture-a",
        "Synthetic research desk A",
        5,
        "fixture-a",
        "https://example.org",
        "Fictional publisher used only for software tests.",
      ],
      [
        "fixture-b",
        "Synthetic research desk B",
        5,
        "fixture-b",
        "https://example.org",
        "Fictional publisher used only for software tests.",
      ],
    ];
    for (const [key, name, tier, group, url, notes] of publishers)
      await put("publishers", {
        id: id(`publisher:${key}`),
        name,
        tier,
        independence_group: group,
        url,
        notes,
      });
    const sources = [
      [
        "sipri25",
        "sipri",
        "SIPRI Yearbook 2025 · World nuclear forces",
        seedSources.sipri25,
        "2025-06-16",
        "en",
        "Yearbook chapter",
        "2025",
        "STALE",
      ],
      [
        "sipri24",
        "sipri",
        "SIPRI Yearbook 2024 · World nuclear forces",
        seedSources.sipri24,
        "2024-06-17",
        "en",
        "Yearbook chapter",
        "2024",
        "SUPERSEDED",
      ],
      [
        "enec",
        "enec",
        "Barakah Unit 4 commences commercial operation",
        seedSources.enec,
        "2024-09-05",
        "en",
        "Official announcement",
        "2024-09-05",
        "ARCHIVED",
      ],
      [
        "france",
        "elysee",
        "Discours sur la stratégie de défense et de dissuasion",
        seedSources.france,
        "2020-02-07",
        "fr",
        "Official speech",
        "2020-02-07",
        "ARCHIVED",
      ],
      [
        "npt",
        "un",
        "NPT · Treaty registration No. 10485",
        seedSources.npt,
        "1970-05-25",
        "en",
        "Treaty record",
        "729-I-10485",
        "ARCHIVED",
      ],
      [
        "scenario-a",
        "fixture-a",
        "Synthetic memo A · programme status",
        "https://example.org/high-profile/fixture-a",
        "2025-01-15",
        "en",
        "Synthetic fixture",
        "1",
        "UNKNOWN",
      ],
      [
        "scenario-b",
        "fixture-b",
        "Synthetic memo B · programme status",
        "https://example.org/high-profile/fixture-b",
        "2025-02-15",
        "en",
        "Synthetic fixture",
        "1",
        "UNKNOWN",
      ],
    ];
    const fragments: Record<string, [string, string, string, boolean][]> = {
      sipri25: [
        [
          "china25",
          "China’s inventory was estimated at up to 600 warheads at the beginning of 2025.",
          "Nuclear weapon modernization trends",
          true,
        ],
        [
          "armed",
          "SIPRI includes China, France, the UK, the USA and Russia among nine nuclear-armed states in its January 2025 assessment.",
          "Opening paragraph",
          true,
        ],
        [
          "modernization",
          "SIPRI describes an ongoing expansion and modernization of China’s nuclear arsenal during 2024.",
          "Nuclear weapon modernization trends",
          true,
        ],
      ],
      sipri24: [
        [
          "china24",
          "The 2024 chapter describes continued expansion and modernization of China’s nuclear stockpile.",
          "Nuclear arsenals",
          true,
        ],
      ],
      enec: [
        [
          "barakah",
          "ENEC announced commercial operation of the fourth Barakah unit on 5 September 2024, bringing all four units into commercial service.",
          "Announcement, opening paragraph",
          true,
        ],
      ],
      france: [
        [
          "fr-count",
          "aujourd’hui inférieure à 300 armes nucléaires",
          "Section on disarmament and strict sufficiency",
          false,
        ],
        [
          "fr-air",
          "The 2020 speech describes strategic air forces and a complementary two-component nuclear force.",
          "Doctrine section, paragraphs on strategic air forces and two components",
          true,
        ],
      ],
      npt: [
        [
          "npt",
          "EIF information: 5 March 1970",
          "Treaty record · EIF information",
          false,
        ],
      ],
      "scenario-a": [
        [
          "scenario-a",
          "SYNTHETIC: The illustrative programme is operating.",
          "Fixture memo A, paragraph 1",
          false,
        ],
      ],
      "scenario-b": [
        [
          "scenario-b",
          "SYNTHETIC: The illustrative programme is suspended.",
          "Fixture memo B, paragraph 1",
          false,
        ],
      ],
    };
    for (const [
      key,
      publisher,
      title,
      url,
      published,
      lang,
      type,
      version,
      health,
    ] of sources) {
      await put("sources", {
        id: id(`source:${key}`),
        publisher_id: id(`publisher:${publisher}`),
        title,
        canonical_url: url,
        published_on: published,
        language: lang,
        document_type: type,
        dataset_version: version,
        health,
        archival_status:
          "Citation and licensed excerpt only; full document not mirrored",
        license: key.startsWith("scenario")
          ? "Project-authored synthetic fixture; MIT"
          : "Copyright retained by publisher. Short excerpt or labeled paraphrase for research citation.",
        is_synthetic: key.startsWith("scenario"),
      });
      await put("source_snapshots", {
        id: id(`snapshot:${key}`),
        source_id: id(`source:${key}`),
        retrieved_at: now,
        content_hash: createHash("sha256")
          .update(JSON.stringify(fragments[key]))
          .digest("hex"),
        hash_scope:
          "Locally retained excerpt/paraphrase manifest only; not a hash of the original document",
        method: key.startsWith("scenario")
          ? "fixture-generation"
          : "manual-reference-review",
        retrieval_note: key.startsWith("scenario")
          ? "Generated synthetic scenario; no external retrieval."
          : "Reference checked using public web source on 17 September 2026. Retained fragments manually entered at seed time; no automated ingestion claimed.",
      });
      for (const [fkey, text, location, paraphrase] of fragments[key])
        await put("evidence_fragments", {
          id: id(`evidence:${fkey}`),
          snapshot_id: id(`snapshot:${key}`),
          original_text: text,
          language: key === "france" && fkey === "fr-air" ? "en" : lang,
          normalized_extraction: text,
          location,
          extraction_method: paraphrase
            ? "editorial-paraphrase"
            : "manual-short-excerpt",
          extracted_at: now,
          is_paraphrase: paraphrase,
        });
    }
    await put("translations", {
      id: id("translation:fr"),
      evidence_id: id("evidence:fr-count"),
      language: "en",
      translated_text: "At that time, fewer than 300 nuclear weapons.",
      engine: "Editorial translation",
      model: "human-authored seed translation",
      confidence: "HIGH",
      reviewed: false,
    });
    const rationale = (authority: string, limitations: string) => ({
      authority,
      independence:
        "One publisher group; no independent corroboration is claimed.",
      directness:
        "The cited passage directly supports this attributed statement.",
      recency:
        "Valid only for the stated effective date. No assertion of current status.",
      limitations,
    });
    const addClaim = async (
      key: string,
      subject: string,
      predicate: string,
      versions: any[],
    ) => {
      await put("claims", {
        id: id(`claim:${key}`),
        subject_id: id(subject),
        predicate,
        first_observed: now,
      });
      for (let i = 0; i < versions.length; i++) {
        const v = versions[i],
          vid = id(`version:${key}:${i + 1}`);
        await put("claim_versions", {
          id: vid,
          claim_id: id(`claim:${key}`),
          version: i + 1,
          statement: v.statement,
          value: v.value ?? {},
          classification: v.classification ?? "ASSESSED",
          confidence: v.confidence ?? "MODERATE",
          confidence_rationale: rationale(
            v.authority ?? "Published specialist research, SIPRI.",
            v.limitations ??
              "Open-source estimate; incomplete disclosure and no direct stockpile verification.",
          ),
          effective_from: v.effective,
          public_on: v.public,
          recorded_at: now,
          reviewed_at: now,
          supersedes_id: i ? id(`version:${key}:${i}`) : null,
          notes:
            v.notes ??
            "Development reference record. Consult the original source and effective date; this is not a live assessment.",
          is_synthetic: !!v.synthetic,
        });
        for (const evidence of v.evidence)
          await put("claim_evidence", {
            version_id: vid,
            evidence_id: id(`evidence:${evidence}`),
            role: "SUPPORTS",
            note: "Source passage supports the attributed statement.",
          });
        for (const evidence of v.contradicts ?? [])
          await put("claim_evidence", {
            version_id: vid,
            evidence_id: id(`evidence:${evidence}`),
            role: "CONTRADICTS",
            note: "Synthetic disagreement retained explicitly.",
          });
        await tx.query("UPDATE claim_versions SET published=true WHERE id=$1", [
          vid,
        ]);
        await put("audit_logs", {
          id: id(`audit:${key}:${i}`),
          action: "CLAIM_PUBLISHED",
          record_id: vid,
          detail: {
            actor: "seed:manual-review",
            fixture: true,
            version: i + 1,
          },
        });
        await put("watch_events", {
          id: id(`watch:${key}:${i}`),
          entity_id: id(subject),
          version_id: vid,
          type: i ? "ASSESSMENT_REVISED" : "CLAIM_ADDED",
          description: v.statement,
          occurred_at: now,
          is_synthetic: !!v.synthetic,
        });
      }
    };
    for (const code of ["CN", "FR", "GB", "US", "RU"])
      await addClaim(`status-${code}`, code, "nuclear_status", [
        {
          statement: `SIPRI assessed ${countries.find((c) => c[0] === code)![1]} as a nuclear-armed state in January 2025.`,
          value: { status: "ASSESSED_NUCLEAR_ARMED" },
          effective: "2025-01-01",
          public: "2025-06-16",
          evidence: ["armed"],
          confidence: "HIGH",
          limitations:
            "Confidence refers to this broad source-attributed status; force size is a separate estimate.",
        },
      ]);
    await addClaim(
      "china-modernization",
      "china-program",
      "programme_assessment",
      [
        {
          statement:
            "SIPRI described continuing expansion and modernization of China’s nuclear stockpile in its 2024 assessment.",
          effective: "2024-01-01",
          public: "2024-06-17",
          evidence: ["china24"],
          confidence: "MODERATE",
        },
        {
          statement:
            "SIPRI assessed that China’s nuclear arsenal expanded and modernized during 2024.",
          effective: "2025-01-01",
          public: "2025-06-16",
          evidence: ["modernization"],
          confidence: "HIGH",
          limitations:
            "Broad direction of change is supported by the source. This does not establish exact force size.",
        },
      ],
    );
    await addClaim("china-estimate", "CN", "warhead_estimate", [
      {
        statement:
          "SIPRI estimated China’s inventory at up to 600 nuclear warheads at the beginning of 2025.",
        value: {
          upper_estimate: 600,
          unit: "warheads",
          scope: "total inventory",
        },
        classification: "ESTIMATED",
        effective: "2025-01-01",
        public: "2025-06-16",
        evidence: ["china25"],
      },
    ]);
    for (const [key, subject] of [
      ["barakah-operation", "barakah"],
      ["unit4-operation", "barakah-4"],
      ["uae-civilian", "AE"],
    ])
      await addClaim(key, subject, "civilian_power_milestone", [
        {
          statement:
            "ENEC announced that Barakah Unit 4 entered commercial operation on 5 September 2024, completing the four-unit fleet.",
          classification: "OFFICIALLY_STATED",
          confidence: "HIGH",
          effective: "2024-09-05",
          public: "2024-09-05",
          evidence: ["barakah"],
          authority: "Official ENEC announcement.",
          limitations:
            "Operator statement. This establishes the 2024 announcement, not live reactor availability.",
        },
      ]);
    await addClaim("france-count", "FR", "historical_arsenal_statement", [
      {
        statement:
          "In February 2020, France’s president stated that the French arsenal contained fewer than 300 nuclear weapons.",
        value: { upper_bound_exclusive: 300 },
        classification: "HISTORICAL",
        confidence: "HIGH",
        effective: "2020-02-07",
        public: "2020-02-07",
        evidence: ["fr-count"],
        authority: "French presidential speech in the original French.",
        limitations:
          "Historical official statement, not an independent count or a current estimate. Translation is editorial and not externally reviewed.",
      },
    ]);
    for (const [key, subject] of [
      ["airborne-role", "airborne"],
      ["france-doctrine", "france-program"],
    ])
      await addClaim(key, subject, "nuclear_role", [
        {
          statement:
            "The 2020 French doctrine speech identified strategic air forces as part of France’s nuclear deterrent.",
          value: {
            role: "CONFIRMED_NUCLEAR_ROLE",
            basis: "official statement, 2020",
          },
          classification: "OFFICIALLY_STATED",
          confidence: "HIGH",
          effective: "2020-02-07",
          public: "2020-02-07",
          evidence: ["fr-air"],
          authority: "Official presidential doctrine statement.",
          limitations:
            "Historical category-level role. No individual aircraft armament, location, readiness or movement is inferred.",
        },
      ]);
    await addClaim("npt-force", "npt", "entered_into_force", [
      {
        statement: "The NPT entered into force on 5 March 1970.",
        classification: "DOCUMENTED",
        confidence: "VERY HIGH",
        effective: "1970-03-05",
        public: "1970-05-25",
        evidence: ["npt"],
        authority: "United Nations treaty registration record.",
        limitations:
          "The record establishes entry into force. It does not establish compliance or current membership.",
      },
    ]);
    await addClaim(
      "scenario-operating",
      "review-scenario",
      "operating_status",
      [
        {
          statement:
            "SYNTHETIC: Memo A describes the illustrative programme as operating.",
          value: { status: "operating" },
          classification: "DISPUTED",
          effective: "2025-01-01",
          public: "2025-02-15",
          evidence: ["scenario-a"],
          contradicts: ["scenario-b"],
          synthetic: true,
          authority: "Fictional test publisher.",
          limitations:
            "Software fixture only. Memo B contradicts the status for the same effective date.",
        },
      ],
    );
    await addClaim(
      "scenario-suspended",
      "review-scenario",
      "operating_status",
      [
        {
          statement:
            "SYNTHETIC: Memo B describes the illustrative programme as suspended.",
          value: { status: "suspended" },
          classification: "REPORTED",
          confidence: "LOW",
          effective: "2025-01-01",
          public: "2025-02-15",
          evidence: ["scenario-b"],
          contradicts: ["scenario-a"],
          synthetic: true,
          authority: "Fictional test publisher.",
          limitations: "Software fixture only. No independent resolution.",
        },
      ],
    );
    await put("claim_contradictions", {
      id: id("contradiction:scenario"),
      left_version_id: id("version:scenario-operating:1"),
      right_version_id: id("version:scenario-suspended:1"),
      explanation:
        "Synthetic reports make mutually exclusive status claims for the same effective date. Neither is selected as truth; both evidence chains remain accessible.",
      status: "OPEN",
    });
    for (const [a, p, b, claim] of [
      ["CN", "associated_with", "china-program", "china-modernization"],
      ["FR", "associated_with", "france-program", "france-doctrine"],
      ["FR", "possesses", "airborne", "airborne-role"],
      ["AE", "associated_with", "barakah", "uae-civilian"],
      ["barakah", "associated_with", "barakah-4", "barakah-operation"],
      ["enec", "associated_with", "barakah", "barakah-operation"],
    ])
      await put("relationships", {
        id: id(`rel:${a}:${b}`),
        subject_id: id(a),
        predicate: p,
        object_id: id(b),
        claim_id: id(`claim:${claim}`),
        note: "Catalog relationship linked to supporting claim; consult its effective date.",
      });
  });
}
