"""History against a real PostgreSQL; runs only when ``TEST_DATABASE_URL`` is set."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import _run_alembic, run_sql
from tests.integration.history_cases import SENSITIVE_VALUES, cipher_requests

pytestmark = pytest.mark.db

EXPECTED_COLUMNS = {
    "id",
    "created_at",
    "cipher",
    "operation",
    "source",
    "response_mode",
    "input_length",
    "output_length",
    "http_status",
    "succeeded",
    "duration_ms",
}


def _insert_rows(url: str, count: int, cipher: str = "caesar", operation: str = "encrypt") -> None:
    run_sql(
        url,
        "INSERT INTO cipher_operations "
        "(created_at, cipher, operation, source, http_status, succeeded, duration_ms) "
        f"SELECT now() - make_interval(secs => n), '{cipher}', '{operation}', 'text', 200, "
        "true, 1 FROM generate_series(1, "
        f"{count}) AS n",
    )


def test_schema_matches_spec(db_url: str) -> None:
    columns = {
        row[0]
        for row in run_sql(
            db_url,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'cipher_operations'",
        )
    }
    indexes = {
        row[0]
        for row in run_sql(
            db_url, "SELECT indexname FROM pg_indexes WHERE tablename = 'cipher_operations'"
        )
    }
    checks = {
        row[0]
        for row in run_sql(
            db_url,
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'cipher_operations'::regclass AND contype = 'c'",
        )
    }

    assert columns == EXPECTED_COLUMNS
    assert {"ix_cipher_operations_created_at_id", "ix_cipher_operations_cipher_created_at"} <= (
        indexes
    )
    assert len(checks) == 7


def test_downgrade_removes_table_and_upgrade_restores_it(db_url: str) -> None:
    exists = "SELECT count(*) FROM pg_tables WHERE tablename = 'cipher_operations'"
    try:
        _run_alembic(db_url, "downgrade", "base")
        assert run_sql(db_url, exists) == [(0,)]
    finally:
        _run_alembic(db_url, "upgrade", "head")
    assert run_sql(db_url, exists) == [(1,)]


def test_every_cipher_route_is_recorded_without_user_content(db_url: str) -> None:
    cases = cipher_requests()
    with TestClient(app) as client:
        for case in cases:
            assert client.post(case.path, **case.kwargs).status_code == 200

    rows = run_sql(db_url, "SELECT cipher, source, operation FROM cipher_operations ORDER BY id")
    assert rows == [(case.cipher, case.source, case.operation) for case in cases]

    dumped = " ".join(
        row[0] for row in run_sql(db_url, "SELECT row_to_json(c)::text FROM cipher_operations c")
    )
    for value in SENSITIVE_VALUES:
        assert value.lower() not in dumped.lower()


def test_failed_request_is_stored(db_url: str) -> None:
    with TestClient(app) as client:
        client.post("/api/vigenere/encrypt", json={"text": "hi", "key": "LE MON"})

    assert run_sql(
        db_url, "SELECT operation, http_status, succeeded, output_length FROM cipher_operations"
    ) == [("encrypt", 422, False, None)]


def test_history_pages_newest_first_without_overlap(db_url: str) -> None:
    _insert_rows(db_url, 25)
    with TestClient(app) as client:
        first = client.get("/api/history").json()["result"]
        second = client.get(f"/api/history?cursor={first['nextCursor']}").json()["result"]

    assert len(first["items"]) == 20
    assert first["nextCursor"] is not None
    assert len(second["items"]) == 5
    assert second["nextCursor"] is None

    items = first["items"] + second["items"]
    assert len({item["id"] for item in items}) == 25
    created = [item["createdAt"] for item in items]
    assert created == sorted(created, reverse=True)
    assert set(items[0]) == {
        "id",
        "createdAt",
        "cipher",
        "operation",
        "source",
        "responseMode",
        "inputLength",
        "outputLength",
        "httpStatus",
        "succeeded",
        "durationMs",
    }


def test_history_limit_and_filters(db_url: str) -> None:
    _insert_rows(db_url, 3, cipher="playfair", operation="decrypt")
    _insert_rows(db_url, 4, cipher="playfair", operation="encrypt")
    _insert_rows(db_url, 2, cipher="caesar", operation="decrypt")
    with TestClient(app) as client:
        filtered = client.get("/api/history?cipher=playfair&operation=decrypt").json()["result"]
        limited = client.get("/api/history?limit=2").json()["result"]

    assert len(filtered["items"]) == 3
    assert all(
        (item["cipher"], item["operation"]) == ("playfair", "decrypt") for item in filtered["items"]
    )
    assert len(limited["items"]) == 2
    assert limited["nextCursor"] is not None


def test_health_reports_ok(db_url: str) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["result"] == {"app": "ok", "database": "ok"}
