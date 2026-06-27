"""Cross-protocol spread calculator — pure deterministic function, no I/O."""

from __future__ import annotations

# ponytail: same LTV usage ratio as looping.py
_LTV_USAGE_RATIO = 0.9

# Default cross-protocol penalty added to risk_score (operating across two
# protocols adds smart-contract and liquidity-gap risk vs. same-protocol loop).
_DEFAULT_CROSS_PROTOCOL_PENALTY = 0.5


def calculate_cross_protocol_spread(
    deposit_apy: float,
    borrow_apy: float,
    max_ltv: float,
    liq_threshold: float,
    cross_protocol_penalty: float = _DEFAULT_CROSS_PROTOCOL_PENALTY,
) -> dict:
    """Compute net spread for a cross-protocol deposit/borrow pair.

    Mirrors simulate_looping geometry but for a single-cycle cross-protocol
    position (deposit on protocol A, borrow same asset on protocol B).

    All APY inputs in percentage units (e.g., 5.0 = 5%).

    Returns:
        net_spread:     deposit_apy - borrow_apy (pre-leverage, percentage pts)
        leverage:       total_deposited / initial_capital
        safety_margin:  liq_threshold - effective_ltv
        risk_score:     heuristic penalty (higher = riskier)
    """
    # One-cycle position: borrow max_ltv * _LTV_USAGE_RATIO of initial capital.
    ltv_used = max_ltv * _LTV_USAGE_RATIO
    effective_ltv = ltv_used  # single cycle, no recursion

    safety_margin = liq_threshold - effective_ltv
    leverage = 1.0 / (1.0 - ltv_used) if ltv_used < 1.0 else 1.0

    net_spread = deposit_apy - borrow_apy

    # Risk: proximity to liquidation + cross-protocol penalty.
    base_risk = 1.0 / safety_margin if safety_margin > 0.0 else 10.0
    risk_score = base_risk + cross_protocol_penalty

    return {
        "net_spread": net_spread,
        "leverage": leverage,
        "safety_margin": safety_margin,
        "risk_score": risk_score,
    }
