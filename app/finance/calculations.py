from __future__ import annotations

from collections.abc import Iterable, Sequence
import math


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def calculate_cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end < 0:
        return None
    return (end / start) ** (1 / years) - 1


def growth_rate(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return current / abs(previous) - 1


def calculate_fcf(operating_cash_flow: float | None, capex: float | None) -> float | None:
    if operating_cash_flow is None or capex is None:
        return None
    return operating_cash_flow - abs(capex)


def calculate_roic(
    operating_income: float | None,
    tax_rate: float | None,
    debt: float | None,
    equity: float | None,
    cash: float | None,
) -> float | None:
    if operating_income is None or debt is None or equity is None or cash is None:
        return None
    effective_tax = 0.21 if tax_rate is None else min(max(tax_rate, 0), 0.5)
    invested_capital = debt + equity - cash
    return safe_divide(operating_income * (1 - effective_tax), invested_capital)


def weighted_average(values: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, float]:
    available = [(values[k], w) for k, w in weights.items() if values.get(k) is not None]
    total_possible = sum(weights.values())
    available_weight = sum(w for _, w in available)
    if not available or available_weight == 0:
        return None, 0.0
    score = sum(float(v) * w for v, w in available) / available_weight
    return round(score, 2), round(available_weight / total_possible, 4)


def consistency(values: Sequence[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    if len(clean) < 3:
        return None
    positive_changes = sum(1 for a, b in zip(clean, clean[1:]) if b >= a)
    return positive_changes / (len(clean) - 1)


def mean(values: Iterable[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(max(value, low), high)


def linear_score(value: float | None, bad: float, good: float, inverse: bool = False) -> float | None:
    if value is None or good == bad:
        return None
    score = (value - bad) / (good - bad) * 100
    score = clamp(score)
    return 100 - score if inverse else score
