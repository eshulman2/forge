"""Shared helpers for persisted per-thread review decisions."""

from typing import Any


def merge_review_decisions(
    previous: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep the latest decision per thread while retaining processed history."""
    merged = {
        item["thread_id"]: item
        for item in previous
        if isinstance(item, dict) and item.get("thread_id")
    }
    merged.update(
        {
            item["thread_id"]: item
            for item in current
            if isinstance(item, dict) and item.get("thread_id")
        }
    )
    return list(merged.values())
