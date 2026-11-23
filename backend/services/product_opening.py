"""Spread the price of an opened sealed product over the cards pulled from it."""

from __future__ import annotations

ALLOCATION_MODES = ("none", "equal", "value")


def allocate_unit_costs(total_cost: float, entries: list[dict], mode: str) -> list[float | None]:
    """Return the cost of ONE copy for each entry.

    ``entries`` carry ``quantity`` and ``value`` (market value of one copy).
    - ``none``: no cost is assigned to the pulled cards.
    - ``equal``: every copy gets the same share.
    - ``value``: copies are weighted by market value (falls back to ``equal``
      when no card has a known value).
    The shares always add back up to ``total_cost`` (rounded to cents, with the
    rounding remainder kept on the most valuable entry).
    """
    if mode not in ALLOCATION_MODES:
        raise ValueError(f"Unknown allocation mode: {mode}")
    if mode == "none" or not entries or total_cost <= 0:
        return [None for _ in entries]

    quantities = [max(int(e.get("quantity") or 0), 0) for e in entries]
    copies = sum(quantities)
    if copies == 0:
        return [None for _ in entries]

    weights = [float(e.get("value") or 0) * q for e, q in zip(entries, quantities)]
    if mode == "equal" or sum(weights) <= 0:
        weights = [float(q) for q in quantities]
    weight_total = sum(weights)

    shares = [round(total_cost * w / weight_total, 2) for w in weights]
    remainder = round(total_cost - sum(shares), 2)
    if remainder:
        heaviest = max(range(len(shares)), key=lambda i: weights[i])
        shares[heaviest] = round(shares[heaviest] + remainder, 2)
    return [round(share / q, 4) if q else None for share, q in zip(shares, quantities)]
