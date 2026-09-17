import csv
import json
import sqlite3

import pytest

from tractor.export.csv_export import export_csv
from tractor.export.json_export import export_json
from tractor.export.report import export_markdown
from tractor.storage.database import Database


def test_database_roundtrip_and_sql_parameterization(database, investigation):
    investigation.query = "'; DROP TABLE investigations; --"
    database.save(investigation)
    loaded = database.load(investigation.id)
    assert loaded.to_dict() == investigation.to_dict()
    assert database.history()[0]["query"] == investigation.query
    assert database.connection.execute("SELECT count(*) FROM records").fetchone()[0] == 1
    with pytest.raises(KeyError):
        database.load("missing")


def test_incomplete_investigations_reopen_as_interrupted(database, investigation):
    investigation.status = "running"
    database.save(investigation)
    assert database.load(investigation.id).status == "interrupted"


def test_newer_database_is_not_silently_downgraded(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="newer"):
        Database(path)


def test_exports_preserve_evidence_and_escape_untrusted_content(tmp_path, investigation, result):
    result.title = '=IMPORTXML("https://malicious.test")'
    result.excerpt = "<script>alert(1)</script> [inject](javascript:alert(1))"
    result.discovery_path = [investigation.id, "query-123", result.id]
    export_json(investigation, tmp_path / "out.json")
    export_csv(investigation, tmp_path / "out.csv")
    export_markdown(investigation, tmp_path / "out.md")
    data = json.loads((tmp_path / "out.json").read_text())
    assert data["results"][0]["discovery_path"] == result.discovery_path
    with (tmp_path / "out.csv").open(encoding="utf-8-sig") as file:
        rows = list(csv.reader(file))
    assert rows[1][1].startswith("'=")
    markdown = (tmp_path / "out.md").read_text()
    assert "<script>" not in markdown
    assert "Source coverage" in markdown and "query-123" in markdown
