"""Tests for calculate_carry — the carry trade calculator."""

from __future__ import annotations

import pytest

from app.calculations.carry import calculate_carry

# ── 1. Positive carry ────────────────────────────────────────────────────────


def test_positive_carry():
    """spot=5%, funding=10%, borrow=3%, fees=0.1% → net_carry=11.9%."""
    result = calculate_carry(spot_yield=5.0, funding_yield=10.0, borrow_cost=3.0, trading_fees=0.1)
    # net_carry = 5 + 10 - 3 - 0.1 = 11.9
    assert result["net_carry"] == pytest.approx(11.9)
    assert result["expected_annual_return"] == pytest.approx(11.9)
    assert result["net_carry"] > 0


# ── 2. Negative carry ────────────────────────────────────────────────────────


def test_negative_carry():
    """spot=1%, funding=-5%, borrow=3%, fees=0.1% → net_carry=-7.1%."""
    result = calculate_carry(spot_yield=1.0, funding_yield=-5.0, borrow_cost=3.0, trading_fees=0.1)
    # net_carry = 1 + (-5) - 3 - 0.1 = -7.1
    assert result["net_carry"] == pytest.approx(-7.1)
    assert result["net_carry"] < 0


# ── 3. Zero-all inputs ───────────────────────────────────────────────────────


def test_zero_all_inputs():
    """All zeros → all zeros, no crash."""
    result = calculate_carry(spot_yield=0.0, funding_yield=0.0, borrow_cost=0.0, trading_fees=0.0)
    assert result["net_carry"] == 0.0
    assert result["risk_score"] == 0.0
    assert result["expected_annual_return"] == 0.0
    assert result["spot_yield"] == 0.0
    assert result["funding_yield"] == 0.0
    assert result["borrow_cost"] == 0.0
    assert result["trading_fees"] == 0.0


# ── 4. Only funding positive ─────────────────────────────────────────────────


def test_only_funding_positive():
    """spot=0, borrow=0, fees=0, funding=8% → net_carry=8%."""
    result = calculate_carry(spot_yield=0.0, funding_yield=8.0, borrow_cost=0.0, trading_fees=0.0)
    assert result["net_carry"] == pytest.approx(8.0)
    # risk_score = abs(8) * 0.3 + abs(0) * 0.2 = 2.4
    assert result["risk_score"] == pytest.approx(2.4)


# ── 5. High trading fees swamp yield ─────────────────────────────────────────


def test_high_fees_swamp_yield():
    """spot=2%, funding=1%, borrow=0, fees=5% → net_carry=-2%."""
    result = calculate_carry(spot_yield=2.0, funding_yield=1.0, borrow_cost=0.0, trading_fees=5.0)
    assert result["net_carry"] == pytest.approx(-2.0)
    assert result["net_carry"] < 0


# ── 6. Risk score monotonic with funding magnitude ───────────────────────────


def test_risk_score_monotonic_funding():
    """Higher abs(funding_yield) → higher risk_score, all else equal."""
    r1 = calculate_carry(spot_yield=5.0, funding_yield=2.0, borrow_cost=1.0, trading_fees=0.0)
    r2 = calculate_carry(spot_yield=5.0, funding_yield=10.0, borrow_cost=1.0, trading_fees=0.0)
    assert r2["risk_score"] > r1["risk_score"]


# ── 7. Deterministic output ──────────────────────────────────────────────────


def test_deterministic_output():
    """Same inputs → identical outputs (no randomness, no external state)."""
    r1 = calculate_carry(spot_yield=6.0, funding_yield=2.5, borrow_cost=1.0, trading_fees=0.2)
    r2 = calculate_carry(spot_yield=6.0, funding_yield=2.5, borrow_cost=1.0, trading_fees=0.2)
    for key in r1:
        assert r1[key] == r2[key], f"non-deterministic: {key} differs"


# ── 8. Version string ────────────────────────────────────────────────────────


def test_calc_version_present():
    """Return dict must include calc_version == 'carry-v1'."""
    result = calculate_carry(spot_yield=5.0, funding_yield=2.0, borrow_cost=1.0, trading_fees=0.0)
    assert result["calc_version"] == "carry-v1"


# ── 9. All expected keys present ─────────────────────────────────────────────


def test_return_dict_has_all_keys():
    """Verify all 8 expected keys present (4 echoes + 3 computed + calc_version)."""
    result = calculate_carry(spot_yield=5.0, funding_yield=2.0, borrow_cost=1.0, trading_fees=0.0)
    expected_keys = {
        "calc_version",
        "spot_yield",
        "funding_yield",
        "borrow_cost",
        "trading_fees",
        "net_carry",
        "risk_score",
        "expected_annual_return",
    }
    actual_keys = set(result.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    assert not missing, f"Missing keys: {missing}"
    assert not extra, f"Unexpected keys: {extra}"


# ── 10. Risk score formula correctness ───────────────────────────────────────


def test_risk_score_formula():
    """risk_score = abs(funding_yield) * 0.3 + abs(borrow_cost) * 0.2."""
    result = calculate_carry(spot_yield=2.0, funding_yield=5.0, borrow_cost=4.0, trading_fees=0.5)
    # abs(5)*0.3 + abs(4)*0.2 = 1.5 + 0.8 = 2.3
    assert result["risk_score"] == pytest.approx(2.3)


def test_risk_score_with_negative_funding():
    """abs() handles negative funding: abs(-8)*0.3 + abs(2)*0.2 = 2.4 + 0.4 = 2.8."""
    result = calculate_carry(spot_yield=3.0, funding_yield=-8.0, borrow_cost=2.0, trading_fees=0.0)
    assert result["risk_score"] == pytest.approx(2.8)


# ── ADEQUACY: Spot yield negative ────────────────────────────────────────────


def test_spot_yield_negative():
    """Negative spot yield reduces net_carry but doesn't crash."""
    result = calculate_carry(spot_yield=-3.0, funding_yield=5.0, borrow_cost=1.0, trading_fees=0.2)
    # net_carry = -3 + 5 - 1 - 0.2 = 0.8
    assert result["net_carry"] == pytest.approx(0.8)


# ── ADEQUACY: Large borrow cost ──────────────────────────────────────────────


def test_large_borrow_cost():
    """High borrow cost creates deep negative carry."""
    result = calculate_carry(spot_yield=2.0, funding_yield=1.0, borrow_cost=15.0, trading_fees=0.5)
    # net_carry = 2 + 1 - 15 - 0.5 = -12.5
    assert result["net_carry"] == pytest.approx(-12.5)
    # risk_score = abs(1)*0.3 + abs(15)*0.2 = 0.3 + 3.0 = 3.3
    assert result["risk_score"] == pytest.approx(3.3)


# ── ADEQUACY: Zero funding ───────────────────────────────────────────────────


def test_zero_funding():
    """funding_yield = 0, risk_score driven purely by borrow_cost."""
    result = calculate_carry(spot_yield=4.0, funding_yield=0.0, borrow_cost=3.0, trading_fees=1.0)
    # net_carry = 4 + 0 - 3 - 1 = 0.0
    assert result["net_carry"] == pytest.approx(0.0)
    # risk_score = abs(0)*0.3 + abs(3)*0.2 = 0.6
    assert result["risk_score"] == pytest.approx(0.6)


# ── ADEQUACY: Expected annual return mirrors net_carry ───────────────────────


def test_expected_annual_return_equals_net_carry():
    """expected_annual_return always equals net_carry."""
    cases = [
        (10.0, 5.0, 2.0, 0.5),
        (1.0, -3.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, -2.0, 1.0, 3.0),
    ]
    for spot, fund, borrow, fees in cases:
        result = calculate_carry(
            spot_yield=spot, funding_yield=fund, borrow_cost=borrow, trading_fees=fees
        )
        assert result["expected_annual_return"] == pytest.approx(result["net_carry"]), (
            f"mismatch for inputs: spot={spot}, funding={fund}, borrow={borrow}, fees={fees}"
        )
