"""Tests for rate_opportunities — the Rating Engine (TDD)."""

from __future__ import annotations

import pytest

from app.calculations.rating import rate_opportunities, rerate_combined


def _opp(**overrides) -> dict:
    """Factory for a pre-scored opportunity dict (ranker output shape)."""
    defaults = {
        "score": 5.0,
        "rank": 1,
        "_protocol": "aave",
        "_history_points": 20,
    }
    return {**defaults, **overrides}


# ── 1. Relative rating scale ─────────────────────────────────────────────────


def test_relative_rating_top_is_100_bottom_is_0_monotonic():
    """Distinct scores → top opp gets rating=100, bottom gets 0, monotonic."""
    opps = [
        _opp(score=1.0),
        _opp(score=3.0),
        _opp(score=5.0),
    ]
    result = rate_opportunities(opps)

    ratings = sorted([r["rating"] for r in result])
    assert ratings[0] == pytest.approx(0.0)
    assert ratings[-1] == pytest.approx(100.0)
    # monotonic: each step is non-decreasing
    assert all(ratings[i] <= ratings[i + 1] for i in range(len(ratings) - 1))


# ── 2. All-equal batch → all 100, no divide-by-zero ─────────────────────────


def test_all_equal_scores_all_get_rating_100():
    """Same score for every opp → all get rating=100 (no ZeroDivisionError)."""
    opps = [_opp(score=4.0) for _ in range(3)]
    result = rate_opportunities(opps)

    for r in result:
        assert r["rating"] == pytest.approx(100.0)


# ── 3. Label thresholds ──────────────────────────────────────────────────────


@pytest.mark.parametrize("rating,expected_label", [
    (90, "Excellent"),
    (85, "Excellent"),   # boundary: ≥85
    (72, "Very Good"),
    (70, "Very Good"),   # boundary: ≥70
    (56, "Good"),
    (55, "Good"),        # boundary: ≥55
    (41, "Fair"),
    (40, "Fair"),        # boundary: ≥40
    (30, "Avoid"),
    (39, "Avoid"),       # just below Fair boundary
])
def test_label_thresholds(rating, expected_label):
    """rating value maps to expected label via thresholds."""
    # Force a two-opp batch so min-max produces the desired rating for opp[0].
    # opp[0] gets rating = (5 - 0) / (5 - 0) * 100 = 100; we test labels directly
    # by constructing a batch where the target rating falls out of min-max.
    # Simpler: single-opp batch (all equal) → rating=100, label=Excellent.
    # Instead, inject rating directly by controlling scores to produce the value.
    #
    # Two opps: scores 0 and X → ratings 0 and 100.
    # For an arbitrary rating R, use scores 0 and 1 for the reference pair,
    # but we can also test label_from_rating separately by inspecting a result
    # that directly produces the target.
    #
    # Cleanest: single opp (equal batch) → 100 → Excellent. That only tests one label.
    # Use a 3-opp batch: scores 0, rating, 100 (scaled as raw scores).
    opps = [
        _opp(score=0.0),
        _opp(score=float(rating)),
        _opp(score=100.0),
    ]
    result = rate_opportunities(opps)
    # Find the opp whose rating matches our target value (score == rating here)
    middle = next(r for r in result if r["score"] == float(rating))
    assert middle["rating"] == pytest.approx(float(rating))
    assert middle["rating_label"] == expected_label


# ── 4. Confidence penalises more stubbed inputs ───────────────────────────────


def test_confidence_penalises_more_stubbed_inputs():
    """Opp with unknown age+audit has lower confidence than one with known age+audit (depth equal)."""
    # "compound" not in PROTOCOL_METADATA → age/audit unknown → more stubs
    # "aave" in PROTOCOL_METADATA with age_known=True, audit_known=True → fewer stubs
    opps = [
        _opp(score=5.0, _protocol="aave", _history_points=20),        # fewer stubs
        _opp(score=5.0, _protocol="unknown_protocol_xyz", _history_points=20),  # more stubs
    ]
    result = rate_opportunities(opps)

    aave_conf = next(r for r in result if r["_protocol"] == "aave")["confidence"]
    unknown_conf = next(r for r in result if r["_protocol"] == "unknown_protocol_xyz")["confidence"]
    assert aave_conf > unknown_conf


# ── 5. Confidence penalises thin history ─────────────────────────────────────


def test_confidence_penalises_thin_history():
    """Same stubbed inputs, n=4 vs n=20 → ~11 vs ~55 confidence (PRD example)."""
    opps = [
        _opp(score=5.0, _protocol="unknown_protocol_xyz", _history_points=4),
        _opp(score=5.0, _protocol="unknown_protocol_xyz", _history_points=20),
    ]
    result = rate_opportunities(opps)

    thin = next(r for r in result if r["_history_points"] == 4)
    mature = next(r for r in result if r["_history_points"] == 20)

    # PRD example: all-stubbed (3 penalties), n=4 → ~11; n=20 → ~55
    assert thin["confidence"] == pytest.approx(11.0, abs=0.5)
    assert mature["confidence"] == pytest.approx(55.0, abs=0.5)


# ── 6. Medals for top 3 ───────────────────────────────────────────────────────


def test_medals_top_3_get_medals_others_none():
    """Top 3 by rating get 🥇🥈🥉; 4th+ get None."""
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


# ── 7. Protocol slug resolves real registered display names ──────────────────


def test_confidence_resolves_display_name_to_slug():
    """Registered name 'Aave V3' must resolve to 'aave' metadata, not miss.

    Regression: maps are keyed by slug; routes pass the full display name. With
    age+audit known, only persistence is stubbed → completeness 0.85, depth 1.0
    → confidence 85 (NOT the 55 a metadata miss would produce).
    """
    opps = [_opp(score=5.0, _protocol="Aave V3", _history_points=20)]
    result = rate_opportunities(opps)
    assert result[0]["confidence"] == pytest.approx(85.0, abs=0.5)


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

    # One shared scale: top score → 100, bottom → 0.
    assert max(o.rating for o in opps) == pytest.approx(100.0)
    assert min(o.rating for o in opps) == pytest.approx(0.0)
    # Exactly one of each medal, gold on the highest score.
    medals = sorted(o.medal for o in opps if o.medal)
    assert medals == sorted(["🥇", "🥈", "🥉"])
    assert next(o for o in opps if o.medal == "🥇").score == 5.0


def test_rerate_combined_empty_is_noop():
    rerate_combined([])  # must not raise
