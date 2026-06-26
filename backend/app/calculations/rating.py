"""Rating Engine — pure function, no I/O.

Layers over ranker.score_opportunities() output to produce:
  rating (0-100, relative min-max), rating_label, confidence (0-100), medal.

Confidence completeness is driven by REAL collected signals attached to each
opp dict by the API route (which reads the Protocol row + a real history-depth
query):

  _protocol_age_days : float | None  days since on-chain deployment, from the
                      ProtocolAgeCollector (binary-search of get_code). None =
                      unknown / not resolvable (e.g. non-EVM protocols like
                      Hyperliquid) -> 1 completeness stub.
  _audit_count      : int            known audit count from the
                      ProtocolAuditCollector (DefiLlama presence today).
                      <= 0 -> 1 stub.
  _persistence_days  : int            distinct calendar days with snapshots in
                      the last 30d. < CONFIDENCE_PERSISTENCE_MIN_DAYS -> 1 stub.
  _history_points   : int            total snapshots in the last 30d; drives the
                      depth factor (min(1, n / CONFIDENCE_VOLATILITY_WINDOW)).

The former static PROTOCOL_METADATA heuristic table is gone — completeness now
reflects what the scanner has actually collected, not a hardcoded allowlist.
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
CONFIDENCE_VOLATILITY_WINDOW = 20  # N snapshots for full depth (matches vol window)
CONFIDENCE_PERSISTENCE_MIN_DAYS = 7  # distinct observation days for persistence_known


# ── Helpers ───────────────────────────────────────────────────────────────────


def _protocol_slug(name: str) -> str:
    """Map a registered protocol display name to its canonical slug key.

    Display names ("Aave V3", "Hyperliquid") -> lowercased first token
    ("aave", "hyperliquid"). Empty/blank names -> "". Shared by the audit
    collector (matches DefiLlama entries by this slug) and tests.
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


def _confidence(
    protocol_age_days: float | None,
    audit_count: int,
    history_points: int,
    persistence_days: int,
) -> float:
    """Compute confidence 0-100 from real collected signals.

    Stubbed inputs (each penalises completeness by CONFIDENCE_STUB_PENALTY,
    floored at CONFIDENCE_COMPLETENESS_FLOOR):
      - protocol_age_days is None        (deployment unknown / not resolvable)
      - audit_count <= 0                (no known audits)
      - persistence_days < MIN          (thin / bursty observation history)

    Depth factor: min(1.0, history_points / CONFIDENCE_VOLATILITY_WINDOW) —
    confidence grows toward 1.0 as we accumulate snapshots.
    """
    stubs = 0
    if protocol_age_days is None:
        stubs += 1
    if audit_count <= 0:
        stubs += 1
    if persistence_days < CONFIDENCE_PERSISTENCE_MIN_DAYS:
        stubs += 1

    completeness = max(CONFIDENCE_COMPLETENESS_FLOOR, 1.0 - stubs * CONFIDENCE_STUB_PENALTY)
    depth = min(1.0, history_points / CONFIDENCE_VOLATILITY_WINDOW)
    return CONFIDENCE_BASE * completeness * depth


# ── Public API ────────────────────────────────────────────────────────────────


def rate_opportunities(scored: list[dict]) -> list[dict]:
    """Attach rating, rating_label, confidence, medal to each scored opp.

    Args:
        scored: output of score_opportunities() — each dict must have 'score'
                and the four real confidence signals (_protocol_age_days,
                _audit_count, _history_points, _persistence_days).

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
            protocol_age_days=opp.get("_protocol_age_days"),
            audit_count=int(opp.get("_audit_count", 0) or 0),
            history_points=int(opp.get("_history_points", 0) or 0),
            persistence_days=int(opp.get("_persistence_days", 0) or 0),
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
