"""Model tier value types, label helpers, and marker parsers.

Pure value-type module with no I/O.  It defines the :class:`ModelTier`
enumeration together with small, focused helpers that translate a tier to and
from its Jira-label form and its body-text marker form.

Design notes
------------
* ``ModelTier`` is a :class:`~enum.StrEnum` so members compare and serialise as
  plain lowercase strings (matching the convention in
  :mod:`forge.models.workflow`).
* Labels use the fixed ``forge:model-tier:`` prefix followed by the bare tier
  value (e.g. ``"forge:model-tier:light"``).  The plain-label namespace
  preserves JQL discoverability (NFR-007) and, together with a single valid
  tier, keeps the exactly-one-valid-tier invariant (BR-004).
* Markers are emitted as the exact single line ``forge.model-tier: {tier}``.
  Parsing scans body text line-by-line and is deliberately
  strict/conservative: only exact-case values in the fixed tier set are
  accepted, everything else yields ``None`` (Section 9.2).

This module must remain free of Jira I/O and must not import
``forge.models.model_policy`` (behavioural isolation, NFR-001/BR-007).
"""

from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "TIER_LABEL_PREFIX",
    "TIER_MARKER_PREFIX",
    "ModelTier",
    "TierEstimate",
    "format_marker",
    "parse_marker_line",
    "parse_tier_label",
    "tier_label",
]

# Prefix used for the plain Jira label, e.g. ``forge:model-tier:heavy``.
TIER_LABEL_PREFIX = "forge:model-tier:"

# Prefix used for the body-text marker line, e.g. ``forge.model-tier: heavy``.
TIER_MARKER_PREFIX = "forge.model-tier:"


class ModelTier(StrEnum):
    """Coarse compute/cost tier assigned to a unit of work.

    Members are ordered from least to most demanding.  Values are lowercase
    strings so the enum round-trips cleanly through labels and markers.
    """

    LIGHT = "light"
    STANDARD = "standard"
    HEAVY = "heavy"
    CRITICAL = "critical"


def tier_label(tier: ModelTier) -> str:
    """Return the prefixed label string for ``tier``.

    For example ``tier_label(ModelTier.LIGHT)`` returns
    ``"forge:model-tier:light"``.
    """
    return f"{TIER_LABEL_PREFIX}{tier.value}"


def parse_tier_label(label: str) -> ModelTier | None:
    """Parse a prefixed tier label back into a :class:`ModelTier`.

    The inverse of :func:`tier_label`.  Returns ``None`` (never raises) for any
    label that is not exactly ``forge:model-tier:`` followed by an in-set,
    exact-case, lowercase value.  Empty, whitespace, wrong-case, out-of-set,
    and unprefixed values all yield ``None`` (BR-004, TS-002, TS-003).
    """
    if not label.startswith(TIER_LABEL_PREFIX):
        return None
    value = label[len(TIER_LABEL_PREFIX) :]
    return _tier_from_value(value)


def format_marker(tier: ModelTier) -> str:
    """Emit the exact marker line ``forge.model-tier: {tier}`` for ``tier``."""
    return f"{TIER_MARKER_PREFIX} {tier.value}"


def parse_marker_line(text: str) -> ModelTier | None:
    """Scan body ``text`` line-by-line for a valid tier marker.

    Returns the tier from the first line of the exact form
    ``forge.model-tier: {tier}`` where ``{tier}`` is an in-set, exact-case
    value.  Missing markers, wrong case, out-of-set values, and otherwise
    unparseable lines yield ``None`` (Section 9.2 conservative handling).
    Round-trips with :func:`format_marker`.
    """
    prefix = f"{TIER_MARKER_PREFIX} "
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :]
        tier = _tier_from_value(value)
        if tier is not None:
            return tier
    return None


def _tier_from_value(value: str) -> ModelTier | None:
    """Return the :class:`ModelTier` for ``value`` or ``None`` if out-of-set."""
    try:
        return ModelTier(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class TierEstimate:
    """Result of a tier estimation: a chosen tier plus supporting reasons.

    The non-empty-``reasons`` invariant is enforced by the estimator, not by
    this value type, which stays a plain immutable carrier.
    """

    tier: ModelTier
    reasons: list[str] = field(default_factory=list)
