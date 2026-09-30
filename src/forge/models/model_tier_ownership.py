"""Ownership resolution and the single-tier-label invariant for model tiers.

Pure value-type / decision module with no I/O.  It consumes the primitives
defined in :mod:`forge.models.model_tier` (the :class:`ModelTier` enum plus the
label / marker helpers) and layers three focused, side-effect-free operations on
top of them:

* :func:`parse_latest_tier_marker` — scan a comment/body text line-by-line and
  return the **last** valid in-set marker's tier (newest-last / latest-wins,
  BR-008).  This is deliberately the opposite selection policy from
  :func:`forge.models.model_tier.parse_marker_line`, which returns the *first*
  valid marker.
* :func:`resolve_tier_ownership` — decide ownership from the tier parsed off the
  latest marker and the tier of the current label (FN-004).  A marker that
  differs from (or is present without) the label takes ownership; a matching
  marker is already in sync; a missing marker keeps whatever the label held.
* :func:`enforce_single_tier` — compute the label adds / removes so that exactly
  one tier label remains after applying the change (BR-004 / FR-007), regardless
  of whether the starting set had zero, one, or multiple tier labels.  Non-tier
  labels are never touched and the caller's list is never mutated.

This module must remain free of Jira I/O and must not import
``forge.models.model_policy`` (behavioural isolation, NFR-001 / BR-007).
"""

from dataclasses import dataclass, field
from typing import Literal

from forge.models.model_tier import (
    ModelTier,
    parse_marker_line,
    tier_label,
)

__all__ = [
    "LabelChange",
    "TierOwnership",
    "enforce_single_tier",
    "parse_latest_tier_marker",
    "resolve_ownership_kind",
    "resolve_tier_ownership",
]


@dataclass(frozen=True)
class TierOwnership:
    """Outcome of an ownership decision: the owning tier plus a change flag.

    ``tier`` is the tier that should own the ticket after reconciliation (or
    ``None`` when neither a marker nor a label is present).  ``changed`` is
    ``True`` only when the marker takes ownership away from the current label
    (including the no-label case); it is ``False`` for an in-sync or no-marker
    outcome.
    """

    tier: ModelTier | None
    changed: bool


@dataclass(frozen=True)
class LabelChange:
    """The label mutations required to enforce the single-tier invariant.

    ``add`` are the labels to apply and ``remove`` the labels to strip so that,
    once both are applied, exactly one tier label remains.  Both default to
    empty (a no-op change).  Only tier labels ever appear here; non-tier labels
    are left untouched.
    """

    add: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)


def parse_latest_tier_marker(text: str) -> ModelTier | None:
    """Return the tier of the **last** valid marker in ``text`` (latest-wins).

    Scans body ``text`` line-by-line and returns the tier from the final line
    of the exact form ``forge.model-tier: {tier}`` where ``{tier}`` is an in-set,
    exact-case value (BR-008).  Later *invalid* markers never override an earlier
    valid one, and a body with no valid marker yields ``None`` (TS-006, TS-007,
    TS-008).  Contrast with :func:`forge.models.model_tier.parse_marker_line`,
    which returns the *first* valid marker.
    """
    latest: ModelTier | None = None
    for line in text.splitlines():
        tier = parse_marker_line(line)
        if tier is not None:
            latest = tier
    return latest


def resolve_tier_ownership(
    marker: ModelTier | None,
    label: ModelTier | None,
) -> TierOwnership:
    """Decide the owning tier from the latest ``marker`` and current ``label``.

    Ownership rules (FN-004, TS-009):

    * no marker present -> the current ``label`` (if any) retains ownership,
      ``changed=False``;
    * marker present and different from the label (including a ``None`` label)
      -> the marker takes ownership, ``changed=True``;
    * marker present and equal to the label -> already in sync, ``changed=False``.
    """
    if marker is None:
        return TierOwnership(tier=label, changed=False)
    return TierOwnership(tier=marker, changed=marker != label)


def resolve_ownership_kind(
    current_label_tier: ModelTier | None,
    latest_marker_tier: ModelTier | None,
) -> Literal["auto-owned", "human-owned"]:
    """Classify ownership as ``"auto-owned"`` or ``"human-owned"`` (FN-004).

    ``"auto-owned"`` only when a marker is present and equals the current label
    tier; any missing marker or marker/label divergence is ``"human-owned"``
    (the caller treats a missing label as assignable).
    """
    if latest_marker_tier is None:
        return "human-owned"
    if latest_marker_tier != current_label_tier:
        return "human-owned"
    return "auto-owned"


def enforce_single_tier(labels: list[str], intended: ModelTier) -> LabelChange:
    """Compute adds / removes leaving exactly one tier label — ``intended``.

    Returns a :class:`LabelChange` such that, after removing ``remove`` and
    adding ``add`` from ``labels``, precisely one tier label remains: the label
    for ``intended`` (BR-004 / FR-007).  Works from zero, one (matching or
    different), or multiple pre-existing tier labels.  Non-tier labels are never
    touched and ``labels`` is not mutated (TS-016).
    """
    desired_label = tier_label(intended)
    all_tier_labels = {tier_label(t) for t in ModelTier}
    present_tier_labels = all_tier_labels.intersection(labels)

    remove = sorted(present_tier_labels - {desired_label})
    add = [] if desired_label in present_tier_labels else [desired_label]
    return LabelChange(add=add, remove=remove)
