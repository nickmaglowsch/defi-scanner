"""Carry trade calculator — pure deterministic function, no I/O."""

from __future__ import annotations


def calculate_carry(
    spot_yield: float,
    funding_yield: float,
    borrow_cost: float,
    trading_fees: float,
) -> dict:
    """Compute net carry from yield/cost components for a carry trade.

    All inputs are in percentage units (e.g., 5.0 = 5%).
    """
    net_carry = spot_yield + funding_yield - borrow_cost - trading_fees
    # ponytail: simple heuristic, volatility from DB added by ranker (task-07)
    risk_score = abs(funding_yield) * 0.3 + abs(borrow_cost) * 0.2

    return {
        "calc_version": "carry-v1",
        "spot_yield": spot_yield,
        "funding_yield": funding_yield,
        "borrow_cost": borrow_cost,
        "trading_fees": trading_fees,
        "net_carry": net_carry,
        "risk_score": risk_score,
        "expected_annual_return": net_carry,
    }
