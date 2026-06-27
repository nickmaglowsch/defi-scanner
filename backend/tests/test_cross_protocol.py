"""Tests for cross-protocol spread calculation (TDD)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.calculations.cross_protocol import calculate_cross_protocol_spread


# ── 1. Pure calculation ───────────────────────────────────────────────────────


def test_positive_spread():
    """deposit_apy=5, borrow_apy=3 → net_spread=2, leverage>1."""
    result = calculate_cross_protocol_spread(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.8,
        liq_threshold=0.85,
    )
    assert result["net_spread"] == pytest.approx(2.0)
    assert result["leverage"] > 1.0
    assert result["safety_margin"] > 0.0
    assert result["risk_score"] > 0.0


def test_zero_spread():
    """Equal rates → net_spread=0."""
    result = calculate_cross_protocol_spread(
        deposit_apy=5.0,
        borrow_apy=5.0,
        max_ltv=0.8,
        liq_threshold=0.85,
    )
    assert result["net_spread"] == pytest.approx(0.0)


def test_negative_spread_still_returns():
    """Inverted spread returns negative net_spread (caller filters)."""
    result = calculate_cross_protocol_spread(
        deposit_apy=2.0,
        borrow_apy=5.0,
        max_ltv=0.8,
        liq_threshold=0.85,
    )
    assert result["net_spread"] < 0.0


def test_risk_score_penalises_cross_protocol():
    """Cross-protocol risk_score > 0 (always penalised for cross-protocol risk)."""
    result = calculate_cross_protocol_spread(
        deposit_apy=10.0,
        borrow_apy=2.0,
        max_ltv=0.8,
        liq_threshold=0.85,
        cross_protocol_penalty=0.5,
    )
    # risk_score incorporates cross-protocol penalty
    result_no_penalty = calculate_cross_protocol_spread(
        deposit_apy=10.0,
        borrow_apy=2.0,
        max_ltv=0.8,
        liq_threshold=0.85,
        cross_protocol_penalty=0.0,
    )
    assert result["risk_score"] > result_no_penalty["risk_score"]


def test_safety_margin_uses_liq_threshold():
    """safety_margin = liq_threshold - effective_ltv."""
    result = calculate_cross_protocol_spread(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.8,
        liq_threshold=0.85,
    )
    # safety_margin must be positive for these inputs
    assert result["safety_margin"] > 0.0
    assert result["safety_margin"] <= 0.85


def test_keys_present():
    """Result must contain all required keys."""
    result = calculate_cross_protocol_spread(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.8,
        liq_threshold=0.85,
    )
    assert "net_spread" in result
    assert "leverage" in result
    assert "safety_margin" in result
    assert "risk_score" in result


# ── 2. Route integration (mocked DB) ─────────────────────────────────────────


def test_cross_protocol_strategy_type_in_opportunity():
    """OpportunityOut constructed with strategy_type='cross_protocol' is valid."""
    from app.schemas.responses import OpportunityOut

    opp = OpportunityOut(
        strategy_type="cross_protocol",
        protocol="Aave V3",
        asset="USDC",
        net_apy=2.0,
        risk_score=1.5,
        score=60.0,
        rank=1,
        strategy_details={
            "deposit_protocol": "Aave V3",
            "deposit_asset": "USDC",
            "borrow_protocol": "Morpho",
            "borrow_asset": "USDC",
            "net_spread": 2.0,
        },
    )
    assert opp.strategy_type == "cross_protocol"
    assert opp.strategy_details["deposit_protocol"] == "Aave V3"
    assert opp.strategy_details["borrow_protocol"] == "Morpho"
