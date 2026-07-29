from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.workflow.utils.review_decisions import (
    decision_matches_comment,
    flatten_review_threads,
    merge_review_decisions,
    reply_to_review_decisions,
)


def test_merge_keeps_latest_decision_per_thread() -> None:
    previous = [
        {"thread_id": "thread-a", "disposition": "reply"},
        {"thread_id": "thread-b", "disposition": "accept"},
    ]
    current = [{"thread_id": "thread-a", "disposition": "accept"}]

    assert merge_review_decisions(previous, current) == [
        {"thread_id": "thread-a", "disposition": "accept"},
        {"thread_id": "thread-b", "disposition": "accept"},
    ]


def test_merge_ignores_items_without_thread_identity() -> None:
    assert merge_review_decisions([{"text": "legacy"}], [{"disposition": "accept"}]) == []


def test_flatten_review_threads_skips_empty_threads() -> None:
    threads = [
        {"thread_id": "empty", "path": "a.py", "line": 1, "comments": []},
        {
            "thread_id": "valid",
            "path": "b.py",
            "line": 2,
            "comments": [{"body": "first"}, {"body": "latest"}],
        },
    ]

    assert flatten_review_threads(threads) == [{"path": "b.py", "line": 2, "body": "latest"}]


def test_decision_matches_original_or_forge_reply_comment() -> None:
    decision = {"comment_id": 10, "forge_reply_id": 11}

    assert decision_matches_comment(decision, 10)
    assert decision_matches_comment(decision, 11)
    assert not decision_matches_comment(decision, 12)


@pytest.mark.asyncio
async def test_reply_records_forge_comment_id() -> None:
    github = MagicMock()
    github.reply_to_review_comment = AsyncMock(return_value={"id": 11})
    github.close = AsyncMock()
    decision = {"comment_id": 10, "response": "Please confirm."}

    with patch("forge.integrations.github.client.GitHubClient", return_value=github):
        await reply_to_review_decisions(
            repo_full_name="org/repo", pr_number=7, decisions=[decision]
        )

    assert decision["forge_reply_id"] == 11
