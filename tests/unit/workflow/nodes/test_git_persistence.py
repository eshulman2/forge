"""Tests for durable Git push policy."""

from unittest.mock import MagicMock, patch

import pytest

from forge.workflow.nodes.git_persistence import (
    PushFailureKind,
    PushPersistenceError,
    classify_push_failure,
    push_to_fork_with_retry,
)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("connection reset by peer", PushFailureKind.TRANSIENT),
        ("request rejected by rate limiter", PushFailureKind.TRANSIENT),
        ("Authentication failed", PushFailureKind.AUTH),
        ("rejected (non-fast-forward)", PushFailureKind.NON_FAST_FORWARD),
        ("invalid refspec", PushFailureKind.PERMANENT),
    ],
)
def test_classify_push_failure(message, expected) -> None:
    assert classify_push_failure(RuntimeError(message)) == expected


@pytest.mark.asyncio
async def test_transient_push_is_retried_without_rerunning_work() -> None:
    git = MagicMock()
    git.push_to_fork.side_effect = [RuntimeError("connection reset"), None]

    with patch("forge.workflow.nodes.git_persistence.asyncio.sleep") as sleep:
        await push_to_fork_with_retry(git)

    assert git.push_to_fork.call_count == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_fast_forward_fails_without_retry() -> None:
    git = MagicMock()
    git.push_to_fork.side_effect = RuntimeError("rejected (non-fast-forward)")

    with pytest.raises(PushPersistenceError) as raised:
        await push_to_fork_with_retry(git)

    assert raised.value.kind == PushFailureKind.NON_FAST_FORWARD
    git.push_to_fork.assert_called_once()
