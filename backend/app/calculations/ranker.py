"""Opportunity ranker — pure scoring function, no I/O."""

PENALTY_KEYS = {"utilization_penalty", "volatility_penalty", "protocol_risk"}


def score_opportunities(opportunities: list[dict], weights: dict) -> list[dict]:
    """Score and rank a list of opportunities using weighted normalized metrics.

    Each opportunity dict must have the keys matching weights:
    yield_score, liquidity_score, tvl_score, stability_score,
    utilization_penalty, volatility_penalty, protocol_risk.

    All metrics are min-max normalized to 0-1 range across the batch.
    Penalty metrics are inverted (1 - normalized) so that higher raw
    penalty → lower normalized score.

    Output is sorted descending by total_score, with ties receiving
    the same rank.
    """
    if not opportunities:
        return []

    metric_keys = list(weights.keys())

    # ── Min-max normalize each metric across the batch ────────────────────────
    metrics_by_key: dict[str, list[float]] = {k: [] for k in metric_keys}
    for opp in opportunities:
        for k in metric_keys:
            metrics_by_key[k].append(float(opp.get(k, 0.0)))

    normalized: list[dict[str, float]] = [{} for _ in opportunities]
    for k in metric_keys:
        vals = metrics_by_key[k]
        min_v = min(vals)
        max_v = max(vals)
        rng = max_v - min_v

        for i, raw in enumerate(vals):
            if rng == 0.0:
                norm = 0.0
            else:
                norm = (raw - min_v) / rng

            if k in PENALTY_KEYS:
                norm = 1.0 - norm

            normalized[i][k] = norm

    # ── Compute total score ───────────────────────────────────────────────────
    for i, opp in enumerate(opportunities):
        total = 0.0
        for k in metric_keys:
            w = weights.get(k, 1.0)
            total += w * normalized[i][k]
        opp["score"] = total
        # ponytail: keep original input fields intact; score and rank are added

    # ── Sort descending by score, assign ranks (ties share rank) ──────────────
    result = sorted(opportunities, key=lambda r: r["score"], reverse=True)

    rank = 0
    prev_score: float | None = None
    for idx, opp in enumerate(result):
        if prev_score is None or opp["score"] != prev_score:
            rank = idx + 1
            prev_score = opp["score"]
        opp["rank"] = rank

    return result
