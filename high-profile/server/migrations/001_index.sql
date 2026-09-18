CREATE TABLE schema_migrations(version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TYPE entity_kind AS ENUM ('COUNTRY','ORGANIZATION','PROGRAM','FACILITY','WEAPON_SYSTEM','DELIVERY_SYSTEM','REACTOR','FUEL_CYCLE_CAPABILITY','TREATY','AGREEMENT','EVENT');
CREATE TYPE claim_class AS ENUM ('DOCUMENTED','OFFICIALLY_STATED','ASSESSED','ESTIMATED','REPORTED','DISPUTED','UNVERIFIED','HISTORICAL','SUPERSEDED','RETRACTED');
CREATE TYPE confidence_level AS ENUM ('VERY HIGH','HIGH','MODERATE','LOW','INSUFFICIENT');
CREATE TYPE source_health AS ENUM ('ACTIVE','STALE','DISCONTINUED','ARCHIVED','SUPERSEDED','UNKNOWN');
CREATE TABLE countries(code char(2) PRIMARY KEY CHECK(code ~ '^[A-Z]{2}$'), name text NOT NULL UNIQUE, region text NOT NULL);
CREATE TABLE entities (
 id uuid PRIMARY KEY, slug text NOT NULL UNIQUE CHECK(slug ~ '^[a-z0-9-]+$'), kind entity_kind NOT NULL,
 name text NOT NULL CHECK(length(name) BETWEEN 1 AND 240), country_code char(2) REFERENCES countries,
 description text NOT NULL DEFAULT '', broad_location text, sensitivity text NOT NULL DEFAULT 'PUBLIC' CHECK(sensitivity IN ('PUBLIC','GENERALIZED')),
 is_synthetic boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now(),
 search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', name || ' ' || description)) STORED
);
CREATE INDEX entities_search_idx ON entities USING gin(search_vector);
CREATE TABLE aliases(id uuid PRIMARY KEY, entity_id uuid NOT NULL REFERENCES entities, alias text NOT NULL, language text NOT NULL, normalized text NOT NULL, UNIQUE(entity_id,normalized));
CREATE INDEX aliases_lookup_idx ON aliases(normalized);
CREATE TABLE publishers(id uuid PRIMARY KEY, name text NOT NULL UNIQUE, tier integer NOT NULL CHECK(tier BETWEEN 1 AND 5), independence_group text NOT NULL, url text NOT NULL CHECK(url ~ '^https://'), notes text NOT NULL);
CREATE TABLE sources (
 id uuid PRIMARY KEY, publisher_id uuid NOT NULL REFERENCES publishers, title text NOT NULL, canonical_url text NOT NULL CHECK(canonical_url ~ '^https://'),
 published_on date NOT NULL, language text NOT NULL CHECK(length(language) BETWEEN 2 AND 35), document_type text NOT NULL,
 dataset_version text, health source_health NOT NULL, archival_status text NOT NULL, license text NOT NULL, is_synthetic boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(canonical_url,dataset_version)
);
CREATE TABLE source_snapshots(id uuid PRIMARY KEY, source_id uuid NOT NULL REFERENCES sources, retrieved_at timestamptz NOT NULL, content_hash text NOT NULL CHECK(content_hash ~ '^[a-f0-9]{64}$'), hash_scope text NOT NULL, method text NOT NULL, storage_key text, retrieval_note text NOT NULL);
CREATE TABLE evidence_fragments(id uuid PRIMARY KEY, snapshot_id uuid NOT NULL REFERENCES source_snapshots, original_text text NOT NULL CHECK(length(original_text)>0), language text NOT NULL, normalized_extraction text NOT NULL, location text NOT NULL, extraction_method text NOT NULL, extracted_at timestamptz NOT NULL, is_paraphrase boolean NOT NULL DEFAULT false, UNIQUE(snapshot_id,location,original_text));
CREATE TABLE translations(id uuid PRIMARY KEY, evidence_id uuid NOT NULL REFERENCES evidence_fragments, language text NOT NULL, translated_text text NOT NULL, engine text NOT NULL, model text NOT NULL, confidence confidence_level, reviewed boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE claims(id uuid PRIMARY KEY, subject_id uuid NOT NULL REFERENCES entities, predicate text NOT NULL, first_observed timestamptz NOT NULL DEFAULT now());
CREATE TABLE claim_versions (
 id uuid PRIMARY KEY, claim_id uuid NOT NULL REFERENCES claims, version integer NOT NULL CHECK(version>0),
 statement text NOT NULL CHECK(length(statement)>0), value jsonb NOT NULL, classification claim_class NOT NULL, confidence confidence_level NOT NULL,
 confidence_rationale jsonb NOT NULL CHECK(jsonb_typeof(confidence_rationale)='object' AND confidence_rationale ? 'authority' AND confidence_rationale ? 'limitations'),
 effective_from date NOT NULL, effective_to date, public_on date NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(), reviewed_at timestamptz NOT NULL DEFAULT now(),
 published boolean NOT NULL DEFAULT false, supersedes_id uuid REFERENCES claim_versions, notes text NOT NULL, is_synthetic boolean NOT NULL DEFAULT false,
 CHECK(effective_to IS NULL OR effective_to>=effective_from), CHECK(public_on<=recorded_at::date), CHECK(reviewed_at>=recorded_at), UNIQUE(claim_id,version)
);
CREATE INDEX claims_subject_idx ON claims(subject_id);
CREATE INDEX claim_versions_history_idx ON claim_versions(claim_id,version DESC);
CREATE TABLE claim_evidence(version_id uuid NOT NULL REFERENCES claim_versions, evidence_id uuid NOT NULL REFERENCES evidence_fragments, role text NOT NULL CHECK(role IN ('SUPPORTS','CONTRADICTS','CONTEXT')), note text NOT NULL, PRIMARY KEY(version_id,evidence_id));
CREATE TABLE claim_contradictions(id uuid PRIMARY KEY, left_version_id uuid NOT NULL REFERENCES claim_versions, right_version_id uuid NOT NULL REFERENCES claim_versions, explanation text NOT NULL, status text NOT NULL CHECK(status IN ('OPEN','METHODOLOGICAL','RESOLVED')), recorded_at timestamptz NOT NULL DEFAULT now(), CHECK(left_version_id<>right_version_id), UNIQUE(left_version_id,right_version_id));
CREATE TABLE relationships(id uuid PRIMARY KEY, subject_id uuid NOT NULL REFERENCES entities, predicate text NOT NULL CHECK(predicate IN ('operates','owns','manages','associated_with','located_in','possesses','assessed_to_possess','formerly_operated','subject_to','party_to','supports_claim','contradicts_claim','supersedes','derived_from','corroborates','references','involved_in','capability_of')), object_id uuid NOT NULL REFERENCES entities, claim_id uuid REFERENCES claims, note text NOT NULL, CHECK(subject_id<>object_id), UNIQUE(subject_id,predicate,object_id));
CREATE TABLE assessments(id uuid PRIMARY KEY, entity_id uuid NOT NULL REFERENCES entities, version_id uuid NOT NULL REFERENCES claim_versions, summary text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE users(id uuid PRIMARY KEY, display_name text NOT NULL, external_identity text UNIQUE);
CREATE TABLE investigations(id uuid PRIMARY KEY, owner_id uuid REFERENCES users, title text NOT NULL, description text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE investigation_items(id uuid PRIMARY KEY, investigation_id uuid NOT NULL REFERENCES investigations, version_id uuid REFERENCES claim_versions, source_id uuid REFERENCES sources, note text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(), CHECK(num_nonnulls(version_id,source_id)=1));
CREATE UNIQUE INDEX investigation_claim_unique ON investigation_items(investigation_id,version_id);
CREATE UNIQUE INDEX investigation_source_unique ON investigation_items(investigation_id,source_id);
CREATE TABLE saved_searches(id uuid PRIMARY KEY, investigation_id uuid REFERENCES investigations, query text NOT NULL, filters jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE watch_events(id uuid PRIMARY KEY, entity_id uuid REFERENCES entities, version_id uuid REFERENCES claim_versions, type text NOT NULL, description text NOT NULL, occurred_at timestamptz NOT NULL, is_synthetic boolean NOT NULL DEFAULT false);
CREATE TABLE ingestion_jobs(id uuid PRIMARY KEY, provider text NOT NULL, status text NOT NULL CHECK(status IN ('QUEUED','RUNNING','REVIEW','FAILED','COMPLETE')), attempts integer NOT NULL DEFAULT 0, error text, source_id uuid REFERENCES sources, started_at timestamptz, finished_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE audit_logs(id uuid PRIMARY KEY, action text NOT NULL, record_id uuid NOT NULL, detail jsonb NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now());

CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Historical provenance records are append-only'; END $$;
CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON sources FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_snapshot BEFORE UPDATE OR DELETE ON source_snapshots FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_evidence BEFORE UPDATE OR DELETE ON evidence_fragments FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_translation BEFORE UPDATE OR DELETE ON translations FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON audit_logs FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE FUNCTION protect_claim_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Claim versions cannot be deleted'; END IF;
 IF TG_OP='UPDATE' AND OLD.published THEN RAISE EXCEPTION 'Published claim versions are immutable'; END IF;
 IF NEW.published THEN
  IF NOT EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id JOIN publishers p ON p.id=s.publisher_id WHERE ce.version_id=NEW.id AND ce.role='SUPPORTS' AND s.published_on<=NEW.public_on AND ss.retrieved_at<=NEW.recorded_at) THEN RAISE EXCEPTION 'Publication requires a complete, dated supporting provenance chain'; END IF;
  IF EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id JOIN source_snapshots ss ON ss.id=ef.snapshot_id JOIN sources s ON s.id=ss.source_id WHERE ce.version_id=NEW.id AND (s.published_on>NEW.public_on OR ss.retrieved_at>NEW.recorded_at OR (s.is_synthetic AND NOT NEW.is_synthetic))) THEN RAISE EXCEPTION 'Evidence timing or fixture classification is invalid'; END IF;
 END IF;
 IF NEW.supersedes_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM claim_versions v WHERE v.id=NEW.supersedes_id AND v.claim_id=NEW.claim_id AND v.version<NEW.version AND v.recorded_at<=NEW.recorded_at) THEN RAISE EXCEPTION 'Invalid supersession chain'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_version BEFORE INSERT OR UPDATE OR DELETE ON claim_versions FOR EACH ROW EXECUTE FUNCTION protect_claim_version();
CREATE FUNCTION protect_claim_evidence() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF EXISTS(SELECT 1 FROM claim_versions WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.version_id ELSE NEW.version_id END AND published) OR (TG_OP='UPDATE' AND EXISTS(SELECT 1 FROM claim_versions WHERE id=OLD.version_id AND published)) THEN RAISE EXCEPTION 'Evidence of published versions is immutable'; END IF;
 RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;
CREATE TRIGGER protect_evidence_link BEFORE INSERT OR UPDATE OR DELETE ON claim_evidence FOR EACH ROW EXECUTE FUNCTION protect_claim_evidence();
INSERT INTO schema_migrations(version) VALUES(1);
