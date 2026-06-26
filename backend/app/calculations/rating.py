"""Rating Engine — pure function, no I/O.

Layers over ranker.score_opportunities() output to produce:
  rating (0-100, relative min-max), rating_label, confidence (0-100), medal.

Each input opp must carry:
  score        — float, from score_opportunities()
  _protocol    — str, lowercase protocol name (wired by task-04)
  _history_points — int, number of history snapshots for this market (task-04)
"""

from __future__ import annotations

# ── Label thresholds ─────────────────────────────────────────────────────────
LABEL_EXCELLENT = 85
LABEL_VERY_GOOD = 70
LABEL_GOOD = 55
LABEL_FAIR = 40

# ── Confidence constants ──────────────────────────────────────────────────────
CONFIDENCE_BASE = 100
CONFIDENCE_STUB_PENALTY = 0.15
CONFIDENCE_COMPLETENESS_FLOOR = 0.4
CONFIDENCE_VOLATILITY_WINDOW = 20  # N — matches DEFI_VOLATILITY_WINDOW default

# ── Protocol metadata ─────────────────────────────────────────────────────────
# ponytail: static placeholder until a real protocol-metadata collector exists.
# Keys: protocol SLUG (lowercased first token of the registered name) →
#   {"age_known": bool, "audit_known": bool}. Protocols register with display
#   names like "Aave V3" / "Hyperliquid"; _protocol_slug() maps those to keys.
# Protocols absent from this map default to age_known=False, audit_known=False.
PROTOCOL_METADATA: dict[str, dict[str, bool]] = {
    "aave": {"age_known": True, "audit_known": True},
    "compound": {"age_known": True, "audit_known": True},
    "hyperliquid": {"age_known": True, "audit_known": False},
    "gmx": {"age_known": True, "audit_known": True},
    "uniswap": {"age_known": True, "audit_known": True},
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _protocol_slug(name: str) -> str:
    """Map a registered protocol name to its metadata key.

    Display names ("Aave V3", "Hyperliquid") → lowercased first token
    ("aave", "hyperliquid"). Empty/blank names → "".
    """
    parts = name.split()
    return parts[0].lower() if parts else ""


def rating_label(rating: float) -> str:
    if rating >= LABEL_EXCELLENT:
        return "Excellent"
    if rating >= LABEL_VERY_GOOD:
        return "Very Good"
    if rating >= LABEL_GOOD:
        return "Good"
    if rating >= LABEL_FAIR:
        return "Fair"
    return "Avoid"


def _confidence(protocol: str, history_points: int) -> float:
    """Compute confidence 0-100.

    completeness_factor: 1.0 - (0.15 × stubbed_count), floor 0.4.
    Stubbed inputs: age_known=False, audit_known=False, persistence (always stubbed).
    depth_factor: min(1.0, n / N).
    """
    meta = PROTOCOL_METADATA.get(_protocol_slug(protocol), {})
    stubs = 0
    if not meta.get("age_known", False):
        stubs += 1
    if not meta.get("audit_known", False):
        stubs += 1
    stubs += 1  # persistence always stubbed

    completeness = max(CONFIDENCE_COMPLETENESS_FLOOR, 1.0 - stubs * CONFIDENCE_STUB_PENALTY)
    depth = min(1.0, history_points / CONFIDENCE_VOLATILITY_WINDOW)
    return CONFIDENCE_BASE * completeness * depth


# ── Public API ────────────────────────────────────────────────────────────────


def rate_opportunities(scored: list[dict]) -> list[dict]:
    """Attach rating, rating_label, confidence, medal to each scored opp.

    Args:
        scored: output of score_opportunities() — each dict must have 'score',
                '_protocol', '_history_points'.

    Returns:
        Same list with rating/rating_label/confidence/medal added in-place.
        Sorted descending by rating (ties preserve input order).
    """
    if not scored:
        return []

    scores = [float(o["score"]) for o in scored]
    min_s = min(scores)
    max_s = max(scores)
    rng = max_s - min_s

    for opp in scored:
        if rng == 0.0:
            opp["rating"] = 100.0
        else:
            opp["rating"] = (float(opp["score"]) - min_s) / rng * 100.0
        opp["rating_label"] = rating_label(opp["rating"])
        opp["confidence"] = _confidence(
            opp.get("_protocol", ""),
            int(opp.get("_history_points", 0)),
        )

    # Sort by rating desc to assign medals
    scored.sort(key=lambda o: o["rating"], reverse=True)

    medals = ["🥇", "🥈", "🥉"]
    for idx, opp in enumerate(scored):
        opp["medal"] = medals[idx] if idx < 3 else None

    return scored


def rerate_combined(opps: list) -> None:
    """Recompute rating/label/medal across a MERGED set of response objects, in place.

    /opportunities?type=all merges loops and carries that were each rated on their
    own per-batch min-max scale with their own 🥇🥈🥉 — not comparable, and medals
    collide. This rerates every object on ONE shared scale (by `.score`) and assigns
    medals to the global top 3. `.confidence` is left untouched (it is per-opportunity,
    not batch-relative). Operates on objects (response models), not dicts.
    """
    if not opps:
        return
    scores = [o.score for o in opps]
    lo, hi = min(scores), max(scores)
    rng = hi - lo
    for o in opps:
        o.rating = 100.0 if rng == 0.0 else (o.score - lo) / rng * 100.0
        o.rating_label = rating_label(o.rating)
        o.medal = None
    medals = ["🥇", "🥈", "🥉"]
    for idx, o in enumerate(sorted(opps, key=lambda x: x.rating, reverse=True)[:3]):
        o.medal = medals[idx]
