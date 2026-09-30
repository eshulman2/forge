"""RED-phase unit tests for JiraClient model-tier labeling methods.

These tests are authored **before** the implementation exists (TDD red-green).
They pin the contract for the four new :class:`JiraClient` tier methods:

* ``apply_tier_label`` — enforce the single ``forge:model-tier:*`` label
  invariant with a single ``PUT /issue/{key}`` carrying combined
  ``update.labels`` add / remove operations (FR-007 / BR-004), and reject
  out-of-set values without mutating labels.
* ``post_tier_comment`` — render a comment whose body carries the verbatim
  marker line ``forge.model-tier: {tier}`` as its own paragraph, a
  human-readable *Why* section (with an explicit demotion basis for ``light``),
  and an *override-instructions* section (FN-003 / Section 9.6 / BR-012 /
  NFR-006).
* ``get_latest_tier_marker`` — reverse-order latest-comment parsing that
  returns the tier from the most recent Forge marker comment, or ``None``
  (FN-006 / BR-008).
* ``resolve_and_maybe_assign_tier`` — Task-only guard (BR-006) and the
  assign / overwrite / no-op ownership branches (SC-004 / SC-005 / SC-006).

The tests deliberately reuse the pure helpers shipped by AISOS-2444
(:mod:`forge.models.model_tier`, :mod:`forge.models.model_tier_estimator`,
:mod:`forge.models.model_tier_ownership`) rather than reimplementing the
estimator / ownership / label logic.

Test-scenario coverage: TS-001, TS-004, TS-005, TS-006, TS-007, TS-008,
TS-009, TS-016.

They FAIL (RED) until ``JiraClient`` grows the four methods above.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.integrations.jira.client import JiraClient

# Reuse AISOS-2444 helpers — do NOT reimplement estimator / ownership / labels.
from forge.models.model_tier import (
    TIER_LABEL_PREFIX,
    ModelTier,
    format_marker,
    tier_label,
)
from forge.models.model_tier_estimator import estimate_tier
from forge.models.model_tier_ownership import parse_latest_tier_marker


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def jira_client() -> JiraClient:
    """Create a JiraClient with mocked settings (no network)."""
    with patch("forge.integrations.jira.client.get_settings") as mock_settings:
        mock_settings.return_value.jira_base_url = "https://test.atlassian.net"
        mock_settings.return_value.jira_api_token = MagicMock()
        mock_settings.return_value.jira_api_token.get_secret_value.return_value = "token"
        mock_settings.return_value.jira_user_email = "test@example.com"
        return JiraClient()


def _mock_http(client: JiraClient) -> AsyncMock:
    """Patch the client's HTTP transport and return the mocked async client.

    Every verb returns a response whose ``raise_for_status`` is a no-op and
    whose ``json`` returns an empty dict, so the tests can inspect the exact
    request payloads the tier methods emit.
    """
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {}

    http = AsyncMock()
    http.put = AsyncMock(return_value=response)
    http.post = AsyncMock(return_value=response)
    http.get = AsyncMock(return_value=response)
    http.request = AsyncMock(return_value=response)
    client._get_client = AsyncMock(return_value=http)  # type: ignore[method-assign]
    return http


def _all_tier_labels() -> set[str]:
    return {tier_label(t) for t in ModelTier}


def _extract_label_ops(payload: dict) -> list[dict]:
    """Return the ``update.labels`` op list from a PUT /issue payload."""
    return payload["update"]["labels"]


# ===========================================================================
# apply_tier_label — single-label invariant (TS-001, TS-016 / FR-007, BR-004)
# ===========================================================================
class TestApplyTierLabel:
    """apply_tier_label enforces exactly one forge:model-tier:* label."""

    @pytest.mark.asyncio
    async def test_single_put_with_combined_add_remove(self, jira_client):
        """A single PUT combines add+remove so exactly one tier label remains.

        Starting from two stale tier labels, applying HEAVY must issue ONE
        ``PUT /issue/{key}`` whose ``update.labels`` removes every other tier
        label and adds the desired one — never a separate add and remove call
        (TS-001 / TS-016 / FR-007 / BR-004).
        """
        http = _mock_http(jira_client)
        jira_client.get_labels = AsyncMock(
            return_value=[
                "forge:managed",
                tier_label(ModelTier.LIGHT),
                tier_label(ModelTier.STANDARD),
            ]
        )

        await jira_client.apply_tier_label("TEST-123", ModelTier.HEAVY)

        # Exactly one PUT to the issue.
        assert http.put.await_count == 1
        call = http.put.await_args
        assert call.args[0] == "/issue/TEST-123"
        ops = _extract_label_ops(call.kwargs["json"])

        added = {op["add"] for op in ops if "add" in op}
        removed = {op["remove"] for op in ops if "remove" in op}

        # The desired tier is added; all other tier labels are removed.
        assert added == {tier_label(ModelTier.HEAVY)}
        assert removed == {tier_label(ModelTier.LIGHT), tier_label(ModelTier.STANDARD)}

        # Non-tier labels are never touched.
        touched = added | removed
        assert "forge:managed" not in touched
        # After the op the resulting tier-label set is exactly one.
        assert len(added) == 1
        assert added <= _all_tier_labels()

    @pytest.mark.asyncio
    async def test_noop_when_desired_label_already_sole_tier(self, jira_client):
        """When the desired tier label is already the only tier label present.

        The method must not add a duplicate; at most it re-affirms the single
        label and never removes it (single-label invariant holds, BR-004).
        """
        http = _mock_http(jira_client)
        jira_client.get_labels = AsyncMock(
            return_value=["forge:managed", tier_label(ModelTier.STANDARD)]
        )

        await jira_client.apply_tier_label("TEST-123", ModelTier.STANDARD)

        if http.put.await_count:
            ops = _extract_label_ops(http.put.await_args.kwargs["json"])
            removed = {op["remove"] for op in ops if "remove" in op}
            # The already-correct tier label must never be removed.
            assert tier_label(ModelTier.STANDARD) not in removed

    @pytest.mark.asyncio
    async def test_rejects_out_of_set_value_without_mutating_labels(self, jira_client):
        """Values outside {light,standard,heavy,critical} are rejected.

        A bad tier string must raise and issue NO ``PUT`` — labels are left
        untouched (BR-004 / conservative handling).
        """
        http = _mock_http(jira_client)
        jira_client.get_labels = AsyncMock(return_value=["forge:managed"])

        with pytest.raises((ValueError, KeyError, TypeError)):
            await jira_client.apply_tier_label("TEST-123", "gigantic")

        assert http.put.await_count == 0

    @pytest.mark.asyncio
    async def test_produced_labels_use_prefix(self, jira_client):
        """Emitted tier labels use the AISOS-2444 forge:model-tier: prefix."""
        http = _mock_http(jira_client)
        jira_client.get_labels = AsyncMock(return_value=[])

        await jira_client.apply_tier_label("TEST-123", ModelTier.CRITICAL)

        ops = _extract_label_ops(http.put.await_args.kwargs["json"])
        added = {op["add"] for op in ops if "add" in op}
        assert added == {tier_label(ModelTier.CRITICAL)}
        assert all(label.startswith(TIER_LABEL_PREFIX) for label in added)


# ===========================================================================
# post_tier_comment — marker + Why + override (TS-004, TS-005 / FN-003, BR-012)
# ===========================================================================
class TestPostTierComment:
    """post_tier_comment renders marker, Why, and override sections."""

    @pytest.mark.asyncio
    async def test_body_contains_verbatim_marker_paragraph(self, jira_client):
        """The verbatim marker line appears as its own paragraph (FN-003)."""
        jira_client.add_comment = AsyncMock(return_value=MagicMock())
        estimate = estimate_tier("Refactor and migrate the auth service concurrency model")

        await jira_client.post_tier_comment("TEST-123", estimate.tier, estimate.reasons)

        body = jira_client.add_comment.await_args.args[1]
        marker = format_marker(estimate.tier)
        assert marker in body
        # Marker stands alone as its own paragraph (blank line before/after or
        # at a body boundary).
        stripped_paragraphs = [p.strip() for p in body.split("\n\n")]
        assert marker in stripped_paragraphs

    @pytest.mark.asyncio
    async def test_body_contains_why_section_with_reasons(self, jira_client):
        """A human-readable Why section lists the estimator reasons (NFR-006)."""
        jira_client.add_comment = AsyncMock(return_value=MagicMock())
        estimate = estimate_tier("Investigate a distributed replication redesign")

        await jira_client.post_tier_comment("TEST-123", estimate.tier, estimate.reasons)

        body = jira_client.add_comment.await_args.args[1]
        assert "Why" in body
        # Every estimator reason is surfaced verbatim in the body.
        for reason in estimate.reasons:
            assert reason in body

    @pytest.mark.asyncio
    async def test_light_tier_body_states_explicit_demotion_basis(self, jira_client):
        """A light-tier comment carries an explicit demotion basis (Section 9.6)."""
        jira_client.add_comment = AsyncMock(return_value=MagicMock())
        estimate = estimate_tier("Fix a typo in a tooltip")
        assert estimate.tier == ModelTier.LIGHT  # guard: estimator picked LIGHT

        await jira_client.post_tier_comment("TEST-123", estimate.tier, estimate.reasons)

        body = jira_client.add_comment.await_args.args[1].lower()
        assert "demot" in body  # "demote" / "demotion" / "demoting"

    @pytest.mark.asyncio
    async def test_body_contains_override_instructions(self, jira_client):
        """An override-instructions section explains how to override (BR-012)."""
        jira_client.add_comment = AsyncMock(return_value=MagicMock())
        estimate = estimate_tier("Standard change with no strong signal")

        await jira_client.post_tier_comment("TEST-123", estimate.tier, estimate.reasons)

        body = jira_client.add_comment.await_args.args[1]
        lowered = body.lower()
        assert "override" in lowered
        # Override instructions reference the tier label mechanism so a human
        # knows exactly how to take ownership (Section 9.6 / NFR-006).
        assert TIER_LABEL_PREFIX in body


# ===========================================================================
# get_latest_tier_marker — reverse-order parsing (TS-006/7/8 / FN-006, BR-008)
# ===========================================================================
class TestGetLatestTierMarker:
    """get_latest_tier_marker returns the newest Forge marker's tier."""

    def _comment(self, body: str):
        c = MagicMock()
        c.body = body
        return c

    @pytest.mark.asyncio
    async def test_returns_tier_from_most_recent_marker_comment(self, jira_client):
        """Reverse-order scan returns the newest marker's tier (BR-008).

        Given chronologically-ordered comments where an older comment marks
        LIGHT and a newer comment marks CRITICAL, the latest tier is CRITICAL
        (TS-006 / TS-007).
        """
        jira_client.get_comments = AsyncMock(
            return_value=[
                self._comment(f"first pass\n\n{format_marker(ModelTier.LIGHT)}"),
                self._comment("a human chimes in with no marker"),
                self._comment(f"re-estimated\n\n{format_marker(ModelTier.CRITICAL)}"),
            ]
        )

        result = await jira_client.get_latest_tier_marker("TEST-123")

        assert result == ModelTier.CRITICAL

    @pytest.mark.asyncio
    async def test_later_invalid_marker_does_not_override_earlier_valid(self, jira_client):
        """A newer *invalid* marker must not clobber an earlier valid one (TS-008)."""
        jira_client.get_comments = AsyncMock(
            return_value=[
                self._comment(f"estimate\n\n{format_marker(ModelTier.HEAVY)}"),
                self._comment("forge.model-tier: gigantic"),  # invalid — ignored
            ]
        )

        result = await jira_client.get_latest_tier_marker("TEST-123")

        assert result == ModelTier.HEAVY

    @pytest.mark.asyncio
    async def test_returns_none_when_no_marker_present(self, jira_client):
        """No Forge marker in any comment yields None (FN-006)."""
        jira_client.get_comments = AsyncMock(
            return_value=[
                self._comment("just a normal human comment"),
                self._comment("another one, still no marker"),
            ]
        )

        result = await jira_client.get_latest_tier_marker("TEST-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_agrees_with_ownership_latest_parser(self, jira_client):
        """The method's result matches the AISOS-2444 latest-marker parser.

        Concatenating comment bodies newest-last and feeding
        :func:`parse_latest_tier_marker` yields the same tier, proving the
        client reuses the shared latest-wins policy rather than a bespoke one.
        """
        bodies = [
            f"{format_marker(ModelTier.STANDARD)}",
            "human note",
            f"{format_marker(ModelTier.HEAVY)}",
        ]
        jira_client.get_comments = AsyncMock(return_value=[self._comment(b) for b in bodies])

        result = await jira_client.get_latest_tier_marker("TEST-123")

        assert result == parse_latest_tier_marker("\n".join(bodies))
        assert result == ModelTier.HEAVY


# ===========================================================================
# resolve_and_maybe_assign_tier — guard + ownership (TS-009 / BR-006, SC-004/5/6)
# ===========================================================================
class TestResolveAndMaybeAssignTier:
    """resolve_and_maybe_assign_tier honours the Task guard and ownership."""

    def _issue(self, issue_type: str, labels: list[str]):
        issue = MagicMock()
        issue.key = "TEST-123"
        issue.issue_type = issue_type
        issue.summary = "Fix a typo in a tooltip"
        issue.description = ""
        issue.labels = labels
        return issue

    @pytest.mark.asyncio
    async def test_task_only_guard_skips_non_task(self, jira_client):
        """Non-Task issues are skipped: no label applied, no comment (BR-006)."""
        jira_client.get_issue = AsyncMock(return_value=self._issue("Epic", []))
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()
        jira_client.get_latest_tier_marker = AsyncMock(return_value=None)

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_not_awaited()
        jira_client.post_tier_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_assigns_when_no_existing_tier(self, jira_client):
        """No marker and no tier label -> estimate and assign (SC-004).

        A Task with no prior tier label / marker gets the estimator's tier
        applied and a marker comment posted.
        """
        jira_client.get_issue = AsyncMock(return_value=self._issue("Task", ["forge:managed"]))
        jira_client.get_latest_tier_marker = AsyncMock(return_value=None)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_awaited_once()
        applied_tier = jira_client.apply_tier_label.await_args.args[1]
        assert applied_tier == estimate_tier("Fix a typo in a tooltip").tier == ModelTier.LIGHT
        jira_client.post_tier_comment.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_comment_failure_leaves_assignment_retryable(self, jira_client):
        """A failed marker comment must not leave an orphan auto-owned label."""
        jira_client.get_issue = AsyncMock(return_value=self._issue("Task", ["forge:managed"]))
        jira_client.get_latest_tier_marker = AsyncMock(return_value=None)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock(side_effect=RuntimeError("comment failed"))

        with pytest.raises(RuntimeError, match="comment failed"):
            await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_recovers_label_from_marker_after_partial_assignment(self, jira_client):
        """An existing marker completes a previously failed label mutation."""
        jira_client.get_issue = AsyncMock(return_value=self._issue("Task", ["forge:managed"]))
        jira_client.get_latest_tier_marker = AsyncMock(return_value=ModelTier.HEAVY)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_awaited_once_with("TEST-123", ModelTier.HEAVY)
        jira_client.post_tier_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_repairs_multiple_tier_labels_preserving_human_override(self, jira_client):
        """Multiple labels converge to the label differing from Forge's marker."""
        jira_client.get_issue = AsyncMock(
            return_value=self._issue(
                "Task",
                [
                    "forge:managed",
                    tier_label(ModelTier.HEAVY),
                    tier_label(ModelTier.LIGHT),
                ],
            )
        )
        jira_client.get_latest_tier_marker = AsyncMock(return_value=ModelTier.HEAVY)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_awaited_once_with("TEST-123", ModelTier.LIGHT)
        jira_client.post_tier_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_op_when_marker_matches_label(self, jira_client):
        """Marker present and equal to the current label -> no-op (SC-006).

        Nothing is re-applied and no new comment is posted when the ticket is
        already in sync.
        """
        existing = tier_label(ModelTier.HEAVY)
        jira_client.get_issue = AsyncMock(
            return_value=self._issue("Task", ["forge:managed", existing])
        )
        jira_client.get_latest_tier_marker = AsyncMock(return_value=ModelTier.HEAVY)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_not_awaited()
        jira_client.post_tier_comment.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_diverged_marker_and_label_is_human_owned_noop(self, jira_client):
        """Marker/label divergence is human-owned and must not clobber (SC-005).

        Forge initially writes a matching marker + label. If a human changes
        only the label (LIGHT) while the Forge marker remains CRITICAL, routine
        resolution must no-op — never push the stale marker onto the label.
        """
        jira_client.get_issue = AsyncMock(
            return_value=self._issue("Task", ["forge:managed", tier_label(ModelTier.LIGHT)])
        )
        jira_client.get_latest_tier_marker = AsyncMock(return_value=ModelTier.CRITICAL)
        jira_client.apply_tier_label = AsyncMock()
        jira_client.post_tier_comment = AsyncMock()

        await jira_client.resolve_and_maybe_assign_tier("TEST-123")

        jira_client.apply_tier_label.assert_not_awaited()
        jira_client.post_tier_comment.assert_not_awaited()
