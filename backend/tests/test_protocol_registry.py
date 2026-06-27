"""Tests for the protocol registry loader and helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.protocols.registry import (
    PROTOCOL_TYPES,
    Registry,
    RegistryEntry,
    RegistryValidationError,
    get_protocol_entries,
    load_registry,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_yaml(tmp_path: Path) -> Path:
    """A minimal valid registry fixture on disk."""
    path = tmp_path / "registry.yaml"
    path.write_text(
        """
version: "2026.06.26"
registry:
  - protocol: Aave V3
    slug: aave-v3
    type: lending
    chain: ethereum
    data_source: rpc
    pool_address: "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    assets:
      USDC: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
      WETH: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
  - protocol: Aave V3
    slug: aave-v3
    type: lending
    chain: arbitrum
    data_source: rpc
    pool_address: "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
    assets:
      USDC: "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
  - protocol: Hyperliquid
    slug: hyperliquid
    type: derivatives
    chain: hyperliquid
    data_source: rest
    pool_address: "https://api.hyperliquid.xyz/info"
    assets:
      BTC: ""
      ETH: ""
""",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_registry(sample_yaml: Path) -> Registry:
    """Loaded registry from the sample fixture."""
    return load_registry(sample_yaml)


# ── load_registry ────────────────────────────────────────────────────────────


def test_load_registry_parses(sample_registry: Registry) -> None:
    assert sample_registry.version == "2026.06.26"
    assert len(sample_registry.entries) == 3
    assert all(isinstance(e, RegistryEntry) for e in sample_registry.entries)


def test_load_registry_entry_fields(sample_registry: Registry) -> None:
    entry = sample_registry.entries[0]
    assert entry.protocol == "Aave V3"
    assert entry.slug == "aave-v3"
    assert entry.type == "lending"
    assert entry.chain == "ethereum"
    assert entry.data_source == "rpc"
    assert entry.pool_address == "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
    assert entry.assets == {
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    }


def test_load_registry_defaults_to_committed_file() -> None:
    """Calling load_registry() with no argument parses the committed YAML."""
    registry = load_registry()
    assert registry.version
    assert len(registry.entries) > 0
    slugs = {e.slug for e in registry.entries}
    assert "aave-v3" in slugs
    assert "hyperliquid" in slugs


# ── get_protocol_entries ─────────────────────────────────────────────────────


def test_get_protocol_entries_by_name(sample_registry: Registry) -> None:
    results = get_protocol_entries(sample_registry, "Aave V3")
    assert len(results) == 2
    assert {r.chain for r in results} == {"ethereum", "arbitrum"}


def test_get_protocol_entries_by_slug(sample_registry: Registry) -> None:
    results = get_protocol_entries(sample_registry, "hyperliquid")
    assert len(results) == 1
    assert results[0].protocol == "Hyperliquid"


def test_get_protocol_entries_filter_by_chain(sample_registry: Registry) -> None:
    results = get_protocol_entries(sample_registry, "Aave V3", chain="arbitrum")
    assert len(results) == 1
    assert results[0].chain == "arbitrum"


def test_get_protocol_entries_no_match(sample_registry: Registry) -> None:
    assert get_protocol_entries(sample_registry, "Unknown") == []
    assert get_protocol_entries(sample_registry, "Aave V3", chain="polygon") == []


# ── Validation ───────────────────────────────────────────────────────────────


def _write_bad_registry(tmp_path: Path, field: str, value: str) -> Path:
    """Build a registry YAML where one string field is set to an invalid value."""
    defaults = {
        "protocol": "X",
        "slug": "x",
        "type": "lending",
        "chain": "ethereum",
        "data_source": "rpc",
    }
    defaults[field] = value
    lines = ['version: "1"', "registry:", "  - " + "\n    ".join(f"{k}: {v}" for k, v in defaults.items())]
    lines.append("    assets:")
    lines.append("      USDC: \"0x0\"")
    path = tmp_path / "bad.yaml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "field, value",
    [
        ("protocol", ""),
        ("slug", ""),
        ("type", ""),
        ("chain", ""),
        ("data_source", ""),
    ],
)
def test_validation_rejects_empty_required_string_field(field: str, value: str, tmp_path: Path) -> None:
    path = _write_bad_registry(tmp_path, field, value)
    with pytest.raises(RegistryValidationError, match=field):
        load_registry(path)


def test_validation_rejects_missing_assets() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(
            """
version: "1"
registry:
  - protocol: Bad
    slug: bad
    type: lending
    chain: ethereum
    data_source: rpc
"""
        )
        f.flush()
        path = Path(f.name)

    with pytest.raises(RegistryValidationError, match="assets"):
        load_registry(path)


def test_validation_rejects_unknown_type() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(
            """
version: "1"
registry:
  - protocol: Bad
    slug: bad
    type: not-a-type
    chain: ethereum
    data_source: rpc
    assets:
      USDC: "0x0"
"""
        )
        f.flush()
        path = Path(f.name)

    with pytest.raises(RegistryValidationError, match="type"):
        load_registry(path)


def test_validation_accepts_all_protocol_types() -> None:
    for t in PROTOCOL_TYPES:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write(
                f"""
version: "1"
registry:
  - protocol: Test
    slug: test
    type: {t}
    chain: ethereum
    data_source: rpc
    assets:
      USDC: "0x0"
"""
            )
            f.flush()
            path = Path(f.name)

        registry = load_registry(path)
        assert registry.entries[0].type == t


def test_validation_rejects_non_dict_assets() -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(
            """
version: "1"
registry:
  - protocol: Bad
    slug: bad
    type: lending
    chain: ethereum
    data_source: rpc
    assets:
      - USDC
"""
        )
        f.flush()
        path = Path(f.name)

    with pytest.raises(RegistryValidationError, match="assets"):
        load_registry(path)


# ── Required protocol coverage ───────────────────────────────────────────────


EXPECTED_PROTOCOLS = {
    "Aave V3",
    "Morpho",
    "Spark",
    "Euler",
    "Fluid",
    "Moonwell",
    "Compound",
    "Silo",
    "Hyperliquid",
    "GMX",
    "Drift",
    "Vertex",
    "dYdX",
}


def test_committed_registry_covers_required_protocols() -> None:
    registry = load_registry()
    names = {e.protocol for e in registry.entries}
    missing = EXPECTED_PROTOCOLS - names
    assert not missing, f"Missing protocols: {missing}"


def test_every_entry_has_required_fields() -> None:
    registry = load_registry()
    for entry in registry.entries:
        assert entry.protocol
        assert entry.slug
        assert entry.type in PROTOCOL_TYPES
        assert entry.chain
        assert entry.data_source
        assert isinstance(entry.assets, dict)
