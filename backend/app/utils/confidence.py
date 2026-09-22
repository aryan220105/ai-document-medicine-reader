from __future__ import annotations


def heuristic_confidence(*parts: float) -> float:
    """Application-level indicator, not a calibrated probability."""
    values = [max(0.0, min(1.0, part)) for part in parts if part is not None]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def is_low(score: float, threshold: float = 0.55) -> bool:
    return score < threshold
