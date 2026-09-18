"""Order ID matching independent of any particular Cases data source."""

from __future__ import annotations


def normalize_order_id(value: str) -> str:
    """Prepare an Order ID for comparison without changing meaningful characters."""
    return value.strip()


def find_all_case_statuses(order_id: str, case_rows: list[list[str]]) -> list[str]:
    """Return a status for every Cases row whose column A matches the Order ID."""
    target = normalize_order_id(order_id)
    if not target:
        return []

    matches: list[str] = []
    for row in case_rows:
        case_order_id = row[0] if row else ""
        if normalize_order_id(case_order_id) == target:
            matches.append(row[6].strip() if len(row) > 6 else "")
    return matches
