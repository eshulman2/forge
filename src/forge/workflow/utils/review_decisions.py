"""Shared helpers for persisted per-thread review decisions."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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


def flatten_review_threads(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the latest comment from each non-empty review thread."""
    return [
        {
            "path": thread.get("path", ""),
            "line": thread.get("line"),
            "body": thread["comments"][-1].get("body", ""),
        }
        for thread in threads
        if thread.get("comments")
    ]


def decision_matches_comment(decision: dict[str, Any], comment_id: int) -> bool:
    """Match either the reviewer comment or Forge's reply in the same thread."""
    return comment_id in (decision.get("comment_id"), decision.get("forge_reply_id"))


async def reply_to_review_decisions(
    *,
    repo_full_name: str,
    pr_number: int | None,
    decisions: list[dict[str, Any]],
    dispositions: set[str] | None = None,
    skip_addressed: bool = False,
) -> None:
    """Reply consistently and retain Forge's reply ID for later correlation."""
    if not repo_full_name or "/" not in repo_full_name or not pr_number or not decisions:
        return

    from forge.integrations.github.client import GitHubClient

    owner, repo = repo_full_name.split("/", 1)
    github = GitHubClient()
    try:
        for decision in decisions:
            if dispositions is not None and decision.get("disposition") not in dispositions:
                continue
            if skip_addressed and decision.get("status") == "addressed":
                continue
            comment_id = decision.get("comment_id")
            response = str(decision.get("response", "")).strip()
            if not isinstance(comment_id, int) or not response:
                continue
            try:
                reply = await github.reply_to_review_comment(
                    owner, repo, pr_number, comment_id, response
                )
                reply_id = reply.get("id") if isinstance(reply, dict) else None
                if isinstance(reply_id, int):
                    decision["forge_reply_id"] = reply_id
            except Exception as exc:
                logger.warning("Failed replying to review comment %s: %s", comment_id, exc)
    finally:
        await github.close()
