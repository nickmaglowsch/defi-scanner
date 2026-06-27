"""Migration tests for the expanded opportunity universe schema."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from urllib.parse import urlparse

import psycopg2
import pytest

# ponytail: use a dedicated test DB so destructive migration tests don't touch
# the developer database. The `defi` user is assumed to have CREATEDB.
TEST_DB_NAME = "defi_scanner_test_migrations"
DEFAULT_DB_URL = "postgresql+asyncpg://defi:defi@localhost:5432/defi_scanner"


def _to_psycopg2_url(asyncpg_url: str) -> str:
    """Convert a SQLAlchemy asyncpg URL into a plain psycopg2 DSN."""
    return asyncpg_url.replace("+asyncpg", "")


def _create_test_db() -> str:
    """Create a fresh test database and return its asyncpg URL."""
    base_url = os.environ.get("DEFI_DATABASE_URL", DEFAULT_DB_URL)
    parsed = urlparse(base_url)
    dsn = (
        f"postgresql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
            cur.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    finally:
        conn.close()

    return base_url.replace(parsed.path, f"/{TEST_DB_NAME}")


def _drop_test_db() -> None:
    """Drop the test database, terminating any open connections first."""
    base_url = os.environ.get("DEFI_DATABASE_URL", DEFAULT_DB_URL)
    parsed = urlparse(base_url)
    dsn = (
        f"postgresql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (TEST_DB_NAME,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    finally:
        conn.close()


def _run_alembic_upgrade(test_db_url: str) -> None:
    """Run `alembic upgrade head` against the test database."""
    env = os.environ.copy()
    env["DEFI_DATABASE_URL"] = test_db_url
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade failed:\n{result.stdout}\n{result.stderr}")


def _table_columns(conn: psycopg2.extensions.connection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return {row[0] for row in cur.fetchall()}


def _foreign_keys(conn: psycopg2.extensions.connection, table: str) -> list[tuple[str, str, str]]:
    """Return (column_name, referenced_table, referenced_column) for table's FKs."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname AS column_name,
                   af.attrelid::regclass::text AS referenced_table,
                   af.attname AS referenced_column
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
            JOIN pg_attribute af ON af.attrelid = c.confrelid AND af.attnum = ANY(c.confkey)
            WHERE c.contype = 'f' AND c.conrelid = %s::regclass
            """,
            (table,),
        )
        return [(row[0], row[1], row[2]) for row in cur.fetchall()]


@pytest.fixture(scope="module")
def migrated_test_db() -> Generator[str, None, None]:
    """Yield the URL of a freshly migrated test database, then drop it."""
    test_url = _create_test_db()
    try:
        _run_alembic_upgrade(test_url)
        yield test_url
    finally:
        _drop_test_db()


def test_market_model_has_chain() -> None:
    from app.models.market import Market

    assert hasattr(Market, "chain")


def test_lending_snapshot_model_has_reward_apy() -> None:
    from app.models.lending_snapshot import LendingSnapshot

    assert hasattr(LendingSnapshot, "reward_apy")


def test_cross_protocol_calculation_model_exists() -> None:
    from app.models.cross_protocol_calculation import CrossProtocolCalculation

    for attr in (
        "id",
        "deposit_market_id",
        "borrow_market_id",
        "calc_version",
        "deposit_apy",
        "borrow_apy",
        "net_spread",
        "leverage",
        "risk_score",
        "created_at",
        "penalty_breakdown",
    ):
        assert hasattr(CrossProtocolCalculation, attr)


def test_loop_and_carry_models_have_penalty_breakdown() -> None:
    from app.models.carry_calculation import CarryCalculation
    from app.models.loop_calculation import LoopCalculation

    assert hasattr(LoopCalculation, "penalty_breakdown")
    assert hasattr(CarryCalculation, "penalty_breakdown")


def test_models_exported_from_init() -> None:
    from app import models

    assert hasattr(models, "CrossProtocolCalculation")


def test_migration_creates_cross_protocol_calculations(migrated_test_db: str) -> None:
    sync_url = _to_psycopg2_url(migrated_test_db)
    with psycopg2.connect(sync_url) as conn:
        columns = _table_columns(conn, "cross_protocol_calculations")
        assert columns == {
            "id",
            "deposit_market_id",
            "borrow_market_id",
            "calc_version",
            "deposit_apy",
            "borrow_apy",
            "net_spread",
            "leverage",
            "risk_score",
            "created_at",
            "penalty_breakdown",
        }

        fks = _foreign_keys(conn, "cross_protocol_calculations")
        assert ("deposit_market_id", "markets", "id") in fks
        assert ("borrow_market_id", "markets", "id") in fks


def test_migration_adds_chain_to_markets(migrated_test_db: str) -> None:
    sync_url = _to_psycopg2_url(migrated_test_db)
    with psycopg2.connect(sync_url) as conn:
        assert "chain" in _table_columns(conn, "markets")


def test_migration_adds_reward_apy_to_lending_snapshots(migrated_test_db: str) -> None:
    sync_url = _to_psycopg2_url(migrated_test_db)
    with psycopg2.connect(sync_url) as conn:
        assert "reward_apy" in _table_columns(conn, "lending_snapshots")


def test_migration_adds_penalty_breakdown_to_calculation_tables(migrated_test_db: str) -> None:
    sync_url = _to_psycopg2_url(migrated_test_db)
    with psycopg2.connect(sync_url) as conn:
        for table in ("loop_calculations", "carry_calculations", "cross_protocol_calculations"):
            assert "penalty_breakdown" in _table_columns(conn, table)
