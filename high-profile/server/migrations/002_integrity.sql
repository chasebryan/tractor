CREATE TRIGGER immutable_publisher BEFORE UPDATE OR DELETE ON publishers FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_claim_identity BEFORE UPDATE OR DELETE ON claims FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER immutable_contradiction BEFORE UPDATE OR DELETE ON claim_contradictions FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE FUNCTION check_snapshot_dates() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM sources s WHERE s.id=NEW.source_id AND s.published_on<=NEW.retrieved_at::date) THEN RAISE EXCEPTION 'Retrieval precedes publication'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER snapshot_dates BEFORE INSERT ON source_snapshots FOR EACH ROW EXECUTE FUNCTION check_snapshot_dates();
CREATE FUNCTION check_extraction_dates() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM source_snapshots s WHERE s.id=NEW.snapshot_id AND s.retrieved_at<=NEW.extracted_at) THEN RAISE EXCEPTION 'Extraction precedes retrieval'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER extraction_dates BEFORE INSERT ON evidence_fragments FOR EACH ROW EXECUTE FUNCTION check_extraction_dates();
CREATE FUNCTION check_published_extraction() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF NEW.published AND EXISTS(SELECT 1 FROM claim_evidence ce JOIN evidence_fragments ef ON ef.id=ce.evidence_id WHERE ce.version_id=NEW.id AND ef.extracted_at>NEW.recorded_at) THEN RAISE EXCEPTION 'Claim predates extraction'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER published_extraction BEFORE INSERT OR UPDATE ON claim_versions FOR EACH ROW EXECUTE FUNCTION check_published_extraction();
CREATE INDEX claim_text_search_idx ON claim_versions USING gin(to_tsvector('english',statement));
