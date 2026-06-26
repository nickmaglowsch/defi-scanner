"""Leveraged looping simulator — pure deterministic function, no I/O."""

from __future__ import annotations

# ponytail: 90% of max LTV per loop, conservative default
LTV_USAGE_RATIO = 0.9


def simulate_looping(
    deposit_apy: float,
    borrow_apy: float,
    max_ltv: float,
    liquidation_threshold: float,
    initial_capital: float,
    target_ltv: float,
    safety_buffer: float,
    max_loops: int,
) -> dict:
    """Simulate recursive deposit→borrow→deposit cycles and compute effective yield.

    All APY inputs are in percentage units (e.g., 5.0 = 5%).
    """
    if initial_capital == 0.0:
        return {
            "calc_version": "loop-v1",
            "input_capital": initial_capital,
            "input_target_ltv": target_ltv,
            "input_safety_buffer": safety_buffer,
            "input_max_loops": max_loops,
            "deposited_capital": 0.0,
            "borrowed_capital": 0.0,
            "net_apy": 0.0,
            "effective_yield": 0.0,
            "leverage": 0.0,
            "safety_margin": liquidation_threshold,
            "liquidation_distance": 100.0,
            "risk_score": 1.0 / liquidation_threshold if liquidation_threshold > 0 else 10.0,
        }

    ltv_used = max_ltv * LTV_USAGE_RATIO
    total_deposited = initial_capital
    total_borrowed = 0.0
    effective_ltv = 0.0

    for _ in range(max_loops):
        borrowable = total_deposited * ltv_used
        new_borrow = borrowable - total_borrowed
        if new_borrow <= 0.0:
            break
        total_borrowed += new_borrow
        total_deposited += new_borrow
        effective_ltv = total_borrowed / total_deposited
        if effective_ltv >= target_ltv * safety_buffer:
            break

    net_apy = (total_deposited * deposit_apy - total_borrowed * borrow_apy) / initial_capital
    safety_margin = liquidation_threshold - effective_ltv

    return {
        "calc_version": "loop-v1",
        "input_capital": initial_capital,
        "input_target_ltv": target_ltv,
        "input_safety_buffer": safety_buffer,
        "input_max_loops": max_loops,
        "deposited_capital": total_deposited,
        "borrowed_capital": total_borrowed,
        "net_apy": net_apy,
        "effective_yield": net_apy,
        "leverage": total_deposited / initial_capital,
        "safety_margin": safety_margin,
        "liquidation_distance": (1.0 - effective_ltv / liquidation_threshold) * 100.0
        if liquidation_threshold > 0.0
        else 0.0,
        "risk_score": 1.0 / safety_margin if safety_margin > 0.0 else 10.0,
    }
