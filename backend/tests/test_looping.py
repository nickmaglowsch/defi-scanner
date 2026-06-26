"""Tests for simulate_looping — the leveraged looping simulator."""

from __future__ import annotations

import pytest

from app.calculations.looping import simulate_looping

# ── Default inputs used across multiple tests ───────────────────────────────

_DEFAULTS = dict(
    deposit_apy=5.0,
    borrow_apy=3.0,
    max_ltv=0.8,
    liquidation_threshold=0.85,
    initial_capital=1000.0,
    target_ltv=0.5,
    safety_buffer=0.95,
    max_loops=10,
)


def _call(**overrides):
    params = {**_DEFAULTS, **overrides}
    return simulate_looping(
        deposit_apy=params["deposit_apy"],
        borrow_apy=params["borrow_apy"],
        max_ltv=params["max_ltv"],
        liquidation_threshold=params["liquidation_threshold"],
        initial_capital=params["initial_capital"],
        target_ltv=params["target_ltv"],
        safety_buffer=params["safety_buffer"],
        max_loops=params["max_loops"],
    )


# ── 1. Single-loop leverage ─────────────────────────────────────────────────


def test_single_loop_leverage_amplifies_yield():
    """5% deposit vs 3% borrow with leverage → net_apy > deposit_apy."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    assert result["net_apy"] > 5.0, f"Expected net_apy > 5%, got {result['net_apy']}"
    assert result["deposited_capital"] > 1000.0
    assert result["borrowed_capital"] > 0.0
    assert result["leverage"] > 1.0


# ── 2. Zero APY spread ──────────────────────────────────────────────────────


def test_zero_spread_no_leverage_benefit():
    """When deposit == borrow APY, looping changes nothing (net_apy == deposit_apy)."""
    result = _call(deposit_apy=5.0, borrow_apy=5.0)
    assert result["net_apy"] == pytest.approx(5.0)


# ── 3. Negative carry ───────────────────────────────────────────────────────


def test_negative_carry_loses_money():
    """Borrow APY > deposit APY → net_apy < deposit_apy."""
    result = _call(deposit_apy=3.0, borrow_apy=5.0)
    assert result["net_apy"] < 3.0


# ── 4. Max loops reached ────────────────────────────────────────────────────


def test_max_loops_enforced():
    """Tiny LTV step + large target → hits max_loops ceiling, terminates."""
    result = _call(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.1,
        target_ltv=0.9,
        max_loops=3,
    )
    # With max_ltv=0.1, ltv_used=0.09 so effective_ltv converges slowly.
    # After 3 loops it should still be far from target, so max_loops terminated it.
    assert result["input_max_loops"] == 3
    # effective_ltv after 3 loops should be well under 0.9
    eff_ltv = result["borrowed_capital"] / result["deposited_capital"]
    assert eff_ltv < 0.5  # nowhere near target


# ── 5. Safety buffer stops early ────────────────────────────────────────────


def test_safety_buffer_stops_before_target():
    """target_ltv=0.8, safety_buffer=0.95 → stops when effective_ltv >= 0.76."""
    result = _call(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.85,
        target_ltv=0.8,
        safety_buffer=0.95,
        max_loops=30,  # enough iterations for asymptotic convergence
    )
    eff_ltv = result["borrowed_capital"] / result["deposited_capital"]
    assert eff_ltv >= 0.76, f"effective_ltv={eff_ltv} should be >= 0.76"
    assert eff_ltv < 0.8, f"effective_ltv={eff_ltv} should be < target (0.8)"


# ── 6. Zero initial capital ─────────────────────────────────────────────────


def test_zero_capital_no_division_by_zero():
    """Zero capital → all zeros, no crash."""
    result = _call(initial_capital=0.0)
    assert result["deposited_capital"] == 0.0
    assert result["borrowed_capital"] == 0.0
    assert result["net_apy"] == 0.0
    assert result["effective_yield"] == 0.0
    assert result["leverage"] == 0.0  # 0/0 → 0


# ── 7. Liquidation distance calculation ─────────────────────────────────────


def test_liquidation_distance_formula():
    """Verify (1 - effective_ltv / liquidation_threshold) * 100."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    eff_ltv = result["borrowed_capital"] / result["deposited_capital"]
    expected_lq_dist = (1 - eff_ltv / 0.85) * 100
    assert result["liquidation_distance"] == pytest.approx(expected_lq_dist)


# ── 8. Deterministic output ─────────────────────────────────────────────────


def test_deterministic_output():
    """Same inputs → identical outputs (no randomness, no external state)."""
    r1 = _call(deposit_apy=6.0, borrow_apy=2.5)
    r2 = _call(deposit_apy=6.0, borrow_apy=2.5)
    for key in r1:
        assert r1[key] == r2[key], f"non-deterministic: {key} differs"


# ── 9. Version string ───────────────────────────────────────────────────────


def test_calc_version_present():
    """Return dict must include calc_version == 'loop-v1'."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    assert result["calc_version"] == "loop-v1"


# ── 10. All expected keys present ───────────────────────────────────────────


def test_return_dict_has_all_keys():
    """Verify all 11 keys (9 output fields + calc_version + input_max_loops)."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    expected_keys = {
        "calc_version",
        "input_capital",
        "input_target_ltv",
        "input_safety_buffer",
        "input_max_loops",
        "deposited_capital",
        "borrowed_capital",
        "net_apy",
        "effective_yield",
        "leverage",
        "safety_margin",
        "liquidation_distance",
        "risk_score",
    }
    actual_keys = set(result.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    assert not missing, f"Missing keys: {missing}"
    assert not extra, f"Unexpected keys: {extra}"


# ── 11. Safety margin correctness ───────────────────────────────────────────


def test_safety_margin():
    """safety_margin = liquidation_threshold - effective_ltv."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    eff_ltv = result["borrowed_capital"] / result["deposited_capital"]
    expected_margin = 0.85 - eff_ltv
    assert result["safety_margin"] == pytest.approx(expected_margin)


# ── 12. Risk score formula ──────────────────────────────────────────────────


def test_risk_score_normal():
    """risk_score = 1 / safety_margin when margin > 0."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    assert result["risk_score"] == pytest.approx(1.0 / result["safety_margin"])


def test_risk_score_zero_margin():
    """risk_score = 10.0 when safety_margin <= 0 (max risk)."""
    # Force a scenario where effective_ltv >= liquidation_threshold
    # by setting liquidation_threshold very low relative to target
    result = _call(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.9,
        liquidation_threshold=0.5,  # below effective_ltv
        target_ltv=0.8,
        safety_buffer=1.0,  # no buffer
    )
    assert result["safety_margin"] <= 0.0
    assert result["risk_score"] == 10.0


# ── 13. LTV clamping: target_ltv > max_ltv ──────────────────────────────────


def test_target_ltv_exceeds_max_ltv_clamped():
    """When target_ltv > max_ltv, effective LTV cannot exceed ltv_used."""
    result = _call(
        deposit_apy=5.0,
        borrow_apy=3.0,
        max_ltv=0.5,
        target_ltv=0.9,  # way above max
        max_loops=50,  # plenty of loops to converge
    )
    eff_ltv = result["borrowed_capital"] / result["deposited_capital"]
    # LTV converges to ltv_used = 0.5 * 0.9 = 0.45; it can never exceed max_ltv
    ltv_used = 0.5 * 0.9
    assert eff_ltv <= ltv_used + 0.01, f"effective_ltv={eff_ltv} exceeds ltv_used={ltv_used}"


# ── 14. Effective yield equals net_apy ──────────────────────────────────────


def test_effective_yield_equals_net_apy():
    """effective_yield mirrors net_apy."""
    result = _call(deposit_apy=7.0, borrow_apy=3.5)
    assert result["effective_yield"] == pytest.approx(result["net_apy"])


# ── 15. Leverage ratio correctness ──────────────────────────────────────────


def test_leverage_ratio():
    """leverage = deposited_capital / initial_capital."""
    result = _call(deposit_apy=5.0, borrow_apy=3.0)
    expected_leverage = result["deposited_capital"] / 1000.0
    assert result["leverage"] == pytest.approx(expected_leverage)


# ── 16. Input passthrough ───────────────────────────────────────────────────


def test_input_passthrough():
    """Input fields are echoed back in the result dict."""
    result = _call(
        deposit_apy=4.0,
        borrow_apy=2.0,
        initial_capital=5000.0,
        target_ltv=0.6,
        safety_buffer=0.9,
        max_loops=7,
    )
    assert result["input_capital"] == 5000.0
    assert result["input_target_ltv"] == 0.6
    assert result["input_safety_buffer"] == 0.9
    assert result["input_max_loops"] == 7
