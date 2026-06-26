"""Tests for rate_opportunities — the Rating Engine (TDD).

Confidence now drives off REAL collected signals (see rating.py docstring):
  _protocol_age_days, _audit_count, _history_points, _persistence_days.
The factory `_opp` defaults to fully-stubbed (age=None, audit=0,
persistence=0) so the inherited non-confidence assertions stay meaningful;
per-test overrides exercise specific real inputs.
"""

from __future__ import annotations

import pytest

from app.calculations.rating import rate_opportunities, rerate_combined


def _opp(**overrides) -> dict:
    """Factory for a pre-scored opportunity dict (ranker output shape).

    Defaults: score=5, _history_points=20, all confidence signals stubbed.
    """
    defaults = {
        "score": 5.0,
        "rank": 1,
        "_protocol": "aave",  # identity only; confidence no longer reads it
        "_history_points": 20,
        "_protocol_age_days": None,   # unknown -> stub
        "_audit_count": 0,            # no audits known -> stub
        "_persistence_days": 0,       # thin -> stub
    }
    return {**defaults, **overrides}


# ── 1. Relative rating scale ─────────────────────────────────────────────────


def test_relative_rating_top_is_100_bottom_is_0_monotonic():
    """Distinct scores -> top opp gets rating=100, bottom gets 0, monotonic."""
    opps = [
        _opp(score=1.0),
        _opp(score=3.0),
        _opp(score=5.0),
    ]
    result = rate_opportunities(opps)

    ratings = sorted([r["rating"] for r in result])
    assert ratings[0] == pytest.approx(0.0)
    assert ratings[-1] == pytest.approx(100.0)
    assert all(ratings[i] <= ratings[i + 1] for i in range(len(ratings) - 1))


# ── 2. All-equal batch -> all 100, no divide-by-zero ─────────────────────────


def test_all_equal_scores_all_get_rating_100():
    """Same score for every opp -> all get rating=100 (no ZeroDivisionError)."""
    opps = [_opp(score=4.0) for _ in range(3)]
    result = rate_opportunities(opps)

    for r in result:
        assert r["rating"] == pytest.approx(100.0)


# ── 3. Label thresholds ──────────────────────────────────────────────────────


@pytest.mark.parametrize("rating,expected_label", [
    (90, "Excellent"),
    (85, "Excellent"),   # boundary: >=85
    (72, "Very Good"),
    (70, "Very Good"),   # boundary: >=70
    (56, "Good"),
    (55, "Good"),        # boundary: >=55
    (41, "Fair"),
    (40, "Fair"),        # boundary: >=40
    (30, "Avoid"),
    (39, "Avoid"),       # just below Fair boundary
])
def test_label_thresholds(rating, expected_label):
    """rating value maps to expected label via thresholds."""
    opps = [
        _opp(score=0.0),
        _opp(score=float(rating)),
        _opp(score=100.0),
    ]
    result = rate_opportunities(opps)
    middle = next(r for r in result if r["score"] == float(rating))
    assert middle["rating"] == pytest.approx(float(rating))
    assert middle["rating_label"] == expected_label


# ── 4. Confidence completeness ladder — one penalty per unknown signal ─────


def test_confidence_zero_stubs_at_full_depth_is_100():
    """All real signals present + history_points >= window -> confidence 100."""
    opps = [_opp(_protocol_age_days=1000.0, _audit_count=3, _persistence_days=25)]
    result = rate_opportunities(opps)
    assert result[0]["confidence"] == pytest.approx(100.0)


def test_confidence_ladder_one_two_three_stubs():
    """Completeness = 0.85 / 0.70 / 0.55 at full depth for 1/2/3 stubs."""
    one = rate_opportunities([_opp(_protocol_age_days=None, _audit_count=3, _persistence_days=25)])
    two = rate_opportunities([_opp(_protocol_age_days=None, _audit_count=0, _persistence_days=25)])
    three = rate_opportunities([_opp()])  # defaults: all stubbed
    assert one[0]["confidence"] == pytest.approx(85.0)
    assert two[0]["confidence"] == pytest.approx(70.0)
    assert three[0]["confidence"] == pytest.approx(55.0)


# ── 5. Confidence penalises thin history (depth) ────────────────────────────


def test_confidence_penalises_thin_history():
    """Fully stubbed completeness, depth 4/20 vs 20/20 -> ~11 vs ~55."""
    thin = rate_opportunities([_opp(_history_points=4)])
    mature = rate_opportunities([_opp(_history_points=20)])
    assert thin[0]["confidence"] == pytest.approx(11.0, abs=0.5)
    assert mature[0]["confidence"] == pytest.approx(55.0, abs=0.5)


def test_confidence_depth_scales_with_history_points():
    """At 0 stubs, depth = n/window -> confidence follows it."""
    q = rate_opportunities([_opp(_history_points=10, _protocol_age_days=1000.0,
                                 _audit_count=3, _persistence_days=25)])
    full = rate_opportunities([_opp(_history_points=20, _protocol_age_days=1000.0,
                                    _audit_count=3, _persistence_days=25)])
    # 10/20 = 0.5 depth * 1.0 completeness -> 50.0
    assert q[0]["confidence"] == pytest.approx(50.0, abs=0.5)
    assert full[0]["confidence"] == pytest.approx(100.0)


# ── 6. Real signals beat stubbed (the slug regression's replacement) ───────


def test_confidence_real_age_and_audit_remove_stubs():
    """Known age + audits + sufficient persistence lift confidence above fully-stubbed.

    Replaces the prior slug-resolution test: completeness is now driven by real
    collected signals, not a static per-protocol allowlist, so the same protocol
    name yields different confidence depending on what the collectors have filled.
    """
    stubbed = rate_opportunities([_opp(_protocol="Aave V3")])[0]["confidence"]
    real = rate_opportunities(
        [_opp(_protocol="Aave V3", _protocol_age_days=1000.0, _audit_count=2, _persistence_days=25)]
    )[0]["confidence"]
    assert stubbed == pytest.approx(55.0, abs=0.5)  # 3 stubs, full depth
    assert real == pytest.approx(100.0)            # 0 stubs, full depth
    assert real > stubbed


# ── 7. Medals for top 3 ───────────────────────────────────────────────────────


def test_medals_top_3_get_medals_others_none():
    """Top 3 by rating get medals; 4th+ get None."""
    opps = [
        _opp(score=1.0),
        _opp(score=2.0),
        _opp(score=3.0),
        _opp(score=4.0),
    ]
    result = rate_opportunities(opps)

    by_rating = sorted(result, key=lambda r: r["rating"], reverse=True)
    assert by_rating[0]["medal"] == "🥇"
    assert by_rating[1]["medal"] == "🥈"
    assert by_rating[2]["medal"] == "🥉"
    assert by_rating[3]["medal"] is None


# ── 8. rerate_combined: one shared scale + unique medals across merged set ───


class _RatedObj:
    """Stand-in for a response model: has .score, mutable rating fields."""

    def __init__(self, score: float) -> None:
        self.score = score
        self.rating: float | None = None
        self.rating_label: str | None = None
        self.medal: str | None = None


def test_rerate_combined_shared_scale_and_unique_medals():
    """Merged loop+carry objects rerated on one scale; exactly one of each medal."""
    opps = [_RatedObj(1.0), _RatedObj(5.0), _RatedObj(3.0), _RatedObj(2.0)]
    rerate_combined(opps)

    assert max(o.rating for o in opps) == pytest.approx(100.0)
    assert min(o.rating for o in opps) == pytest.approx(0.0)
    medals = sorted(o.medal for o in opps if o.medal)
    assert medals == sorted(["🥇", "🥈", "🥉"])
    assert next(o for o in opps if o.medal == "🥇").score == 5.0


def test_rerate_combined_empty_is_noop():
    rerate_combined([])  # must not raise
