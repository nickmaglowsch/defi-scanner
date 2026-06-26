"""Tests for score_opportunities — the opportunity ranker (TDD)."""

from __future__ import annotations

from app.calculations.ranker import score_opportunities

_DEFAULT_WEIGHTS = {
    "yield_score": 1.0,
    "liquidity_score": 1.0,
    "tvl_score": 1.0,
    "stability_score": 1.0,
    "utilization_penalty": 1.0,
    "volatility_penalty": 1.0,
    "protocol_risk": 1.0,
}


def _opp(**overrides) -> dict:
    """Factory for an opportunity dict with sensible defaults."""
    defaults = {
        "yield_score": 5.0,
        "liquidity_score": 3.0,
        "tvl_score": 2.0,
        "stability_score": 4.0,
        "utilization_penalty": 0.2,
        "volatility_penalty": 0.1,
        "protocol_risk": 0.3,
    }
    return {**defaults, **overrides}


# ── 1. Basic ranking ──────────────────────────────────────────────────────────


def test_basic_ranking_highest_yield_gets_rank_1():
    """3 opportunities with different yields → highest yield gets rank 1."""
    opps = [
        _opp(yield_score=1.0),
        _opp(yield_score=5.0),
        _opp(yield_score=3.0),
    ]
    weights = _DEFAULT_WEIGHTS
    result = score_opportunities(opps, weights)

    assert len(result) == 3
    # Highest yield_score=5.0 should be rank 1 (all other metrics identical)
    ranked = sorted(result, key=lambda r: r["rank"])
    assert ranked[0]["yield_score"] == 5.0
    assert ranked[0]["rank"] == 1
    assert ranked[1]["rank"] == 2
    assert ranked[2]["rank"] == 3


# ── 2. Equal scores → same rank ───────────────────────────────────────────────


def test_equal_scores_same_rank():
    """2 opportunities with identical metrics → share same rank."""
    opps = [
        _opp(yield_score=5.0),
        _opp(yield_score=5.0),  # identical
    ]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)

    assert len(result) == 2
    assert result[0]["rank"] == result[1]["rank"] == 1
    assert result[0]["score"] == result[1]["score"]


# ── 3. Empty input ────────────────────────────────────────────────────────────


def test_empty_input_returns_empty_list():
    """Empty opportunity list → empty list returned."""
    result = score_opportunities([], _DEFAULT_WEIGHTS)
    assert result == []


# ── 4. Single opportunity ─────────────────────────────────────────────────────


def test_single_opportunity_gets_rank_1():
    """One item → rank 1, normalized values handled (no division by zero)."""
    opps = [_opp(yield_score=7.0)]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)

    assert len(result) == 1
    assert result[0]["rank"] == 1
    assert "score" in result[0]
    assert isinstance(result[0]["score"], float)


# ── 5. Weight influence ──────────────────────────────────────────────────────


def test_weight_influence_yield_dominates():
    """weight on yield_score=10, liquidity=0 → yield dominates ranking."""
    opps = [
        _opp(yield_score=1.0, liquidity_score=100.0),
        _opp(yield_score=10.0, liquidity_score=1.0),
    ]
    weights = {**_DEFAULT_WEIGHTS, "yield_score": 10.0, "liquidity_score": 0.0}

    result = score_opportunities(opps, weights)
    # Even though opp[0] has huge liquidity_score, weight 0 makes it irrelevant
    # opp[1] has higher yield → should be rank 1
    assert result[0]["rank"] == 1
    assert result[0]["yield_score"] == 10.0


# ── 6. Penalty inversion ─────────────────────────────────────────────────────


def test_penalty_inversion_higher_penalty_lower_score():
    """Higher utilization_penalty → lower total score (all else equal)."""
    opps = [
        _opp(utilization_penalty=0.1, volatility_penalty=0.0, protocol_risk=0.0),
        _opp(utilization_penalty=0.9, volatility_penalty=0.0, protocol_risk=0.0),
    ]
    # Only utilization_penalty differs, weight=1 for everything
    weights = _DEFAULT_WEIGHTS
    result = score_opportunities(opps, weights)

    # The one with utilization_penalty=0.1 should rank higher (penalty inverted)
    assert result[0]["rank"] == 1
    assert result[0]["utilization_penalty"] == 0.1
    assert result[1]["utilization_penalty"] == 0.9
    assert result[0]["score"] > result[1]["score"]


# ── 7. Deterministic output ──────────────────────────────────────────────────


def test_deterministic_output_same_input_same_output():
    """Same inputs + weights → identical output (no randomness)."""
    opps = [
        _opp(yield_score=6.0, liquidity_score=3.0, tvl_score=4.0),
        _opp(yield_score=2.0, liquidity_score=7.0, tvl_score=1.0),
        _opp(yield_score=8.0, liquidity_score=2.0, tvl_score=5.0),
    ]
    r1 = score_opportunities(opps, _DEFAULT_WEIGHTS)
    r2 = score_opportunities(opps, _DEFAULT_WEIGHTS)

    for i in range(len(r1)):
        for key in r1[i]:
            assert r1[i][key] == r2[i][key], f"non-deterministic: [{i}][{key}] differs"


# ── 8. All penalties inverted correctly ───────────────────────────────────────


def test_all_penalty_metrics_reduce_score():
    """volatility_penalty and protocol_risk also invert (higher raw → lower score)."""
    opps = [
        _opp(volatility_penalty=0.0, protocol_risk=0.0, utilization_penalty=0.0),
        _opp(volatility_penalty=1.0, protocol_risk=0.0, utilization_penalty=0.0),
    ]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)
    assert result[0]["volatility_penalty"] == 0.0  # rank 1
    assert result[0]["score"] > result[1]["score"]


def test_protocol_risk_inversion():
    """Higher protocol_risk → lower score."""
    opps = [
        _opp(protocol_risk=0.0, utilization_penalty=0.0, volatility_penalty=0.0),
        _opp(protocol_risk=1.0, utilization_penalty=0.0, volatility_penalty=0.0),
    ]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)
    assert result[0]["protocol_risk"] == 0.0
    assert result[0]["score"] > result[1]["score"]


# ── 9. All identical → all same rank ──────────────────────────────────────────


def test_all_identical_all_same_rank():
    """Multiple opportunities with identical raw metrics → all rank 1, same score."""
    opps = [
        _opp(yield_score=5.0, liquidity_score=3.0),
        _opp(yield_score=5.0, liquidity_score=3.0),
        _opp(yield_score=5.0, liquidity_score=3.0),
    ]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)

    scores = [r["score"] for r in result]
    ranks = [r["rank"] for r in result]
    assert len(set(scores)) == 1, "all should have same score"
    assert len(set(ranks)) == 1, "all should have same rank"
    assert ranks[0] == 1


# ── 10. Output contains required keys ─────────────────────────────────────────


def test_output_contains_required_keys():
    """Each result dict has 'score', 'rank' plus all input keys preserved."""
    opps = [_opp()]
    result = score_opportunities(opps, _DEFAULT_WEIGHTS)

    item = result[0]
    assert "score" in item
    assert "rank" in item
    # all original input keys preserved
    for k in ("yield_score", "liquidity_score", "tvl_score", "stability_score",
              "utilization_penalty", "volatility_penalty", "protocol_risk"):
        assert k in item, f"missing key: {k}"
