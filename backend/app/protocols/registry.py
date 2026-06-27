"""Human-editable YAML protocol registry and loader.

The registry is the single source of truth for which protocols, chains, and
assets the scanner monitors. Adapters and collectors import from here instead
of scattering addresses across env vars.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

# Valid protocol categories. Keep in sync with app.models.protocol.Protocol.type.
PROTOCOL_TYPES = ("lending", "derivatives", "staking", "restaking", "pendle")


class RegistryValidationError(ValueError):
    """Raised when a registry entry fails validation."""


@dataclass(frozen=True)
class RegistryEntry:
    """One protocol deployment on one chain."""

    protocol: str
    slug: str
    type: str
    chain: str
    data_source: str
    assets: dict[str, str]
    pool_address: str | None = None
    rpc_url: str | None = None
    notes: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class Registry:
    """Top-level container parsed from registry.yaml."""

    version: str
    entries: list[RegistryEntry]


def _default_registry_path() -> Path:
    """Resolve the committed registry relative to this module."""
    return Path(__file__).with_suffix(".yaml")


def _validate_entry(entry: dict[str, Any], index: int) -> None:
    """Ensure a raw YAML entry has the required shape."""
    required_strings = ("protocol", "slug", "type", "chain", "data_source")
    for field in required_strings:
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RegistryValidationError(
                f"Entry {index}: missing or empty required field '{field}'"
            )

    if entry["type"] not in PROTOCOL_TYPES:
        raise RegistryValidationError(
            f"Entry {index}: invalid type '{entry['type']}'. "
            f"Must be one of {PROTOCOL_TYPES}"
        )

    assets = entry.get("assets")
    if not isinstance(assets, dict) or not all(isinstance(k, str) for k in assets):
        raise RegistryValidationError(
            f"Entry {index}: 'assets' must be a symbol -> address mapping"
        )


def _build_entry(entry: dict[str, Any], index: int) -> RegistryEntry:
    """Validate and materialize one raw YAML entry."""
    _validate_entry(entry, index)
    return RegistryEntry(
        protocol=entry["protocol"].strip(),
        slug=entry["slug"].strip(),
        type=entry["type"].strip(),
        chain=entry["chain"].strip(),
        data_source=entry["data_source"].strip(),
        assets={k: str(v) for k, v in entry.get("assets", {}).items()},
        pool_address=entry.get("pool_address") or None,
        rpc_url=entry.get("rpc_url") or None,
        notes=entry.get("notes") or None,
        enabled=bool(entry.get("enabled", True)),
    )


def load_registry(path: Path | str | None = None) -> Registry:
    """Load and validate the protocol registry from YAML.

    Args:
        path: YAML file to load. Defaults to the committed registry.yaml next
            to this module, or the path from DEFI_PROTOCOL_REGISTRY_PATH.
    """
    if path is None:
        configured = settings.DEFI_PROTOCOL_REGISTRY_PATH
        path = Path(configured) if configured else _default_registry_path()
    else:
        path = Path(path)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RegistryValidationError("Registry YAML must be a mapping")

    version = str(raw.get("version", ""))
    raw_entries = raw.get("registry", [])
    if not isinstance(raw_entries, list):
        raise RegistryValidationError("'registry' must be a list of entries")

    entries = [_build_entry(entry, i) for i, entry in enumerate(raw_entries)]
    return Registry(version=version, entries=entries)


def get_protocol_entries(
    registry: Registry,
    protocol: str,
    chain: str | None = None,
) -> list[RegistryEntry]:
    """Return registry entries matching a protocol name or slug.

    Args:
        registry: Parsed registry.
        protocol: Display name (e.g. "Aave V3") or slug (e.g. "aave-v3").
        chain: Optional chain filter.

    Returns:
        Matching entries, preserving YAML order.
    """
    matches = [
        e
        for e in registry.entries
        if e.protocol == protocol or e.slug == protocol
    ]
    if chain is not None:
        matches = [e for e in matches if e.chain == chain]
    return matches
