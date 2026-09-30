"""Deterministic keyword/signal-based model-tier estimator.

Pure heuristic that inspects the free text of a unit of work (a summary and an
optional description) and returns a :class:`~forge.models.model_tier.TierEstimate`
— a chosen :class:`~forge.models.model_tier.ModelTier` plus a **non-empty** list
of human-readable ``reasons`` explaining the decision (Section 10.5).

Design notes
------------
* :func:`estimate_tier` is a **pure function**: no logging, no I/O, no Jira, and
  no hidden state.  Repeated calls on identical inputs return an identical tier
  and identical reasons (deterministic, NFR-005 / TS-019).
* All keyword/signal sets, weights, thresholds, and the long/short description
  length threshold are **module-level tunable constants** so the heuristic can
  be retuned without touching control flow (NFR-002, BR-010).
* Matching is case-insensitive over ``summary + "\\n" + description``.  Empty or
  whitespace-only input records the baseline ``STANDARD`` reason (Section 5
  empty-text row).
* Follows the pure, side-effect-free style of :mod:`forge.models.model_policy`;
  it must not import ``model_policy`` (behavioural isolation).

Algorithm order (Section 10.5)
------------------------------
1. Start from the baseline :data:`~forge.models.model_tier.ModelTier.STANDARD`
   and always append a baseline reason.
2. Security / auth / crypto / permission / migration / data-integrity signals
   escalate to ``CRITICAL``.
3. Refactor / multi-service / schema / API-break signals, a long description, or
   complexity keywords escalate to ``HEAVY``.
4. Small / isolated / UI-copy signals paired with a short description demote to
   ``LIGHT`` with explicit demotion reasons.
5. ``reasons`` is always non-empty.
"""

from forge.models.model_tier import ModelTier, TierEstimate

__all__ = [
    "COMPLEXITY_KEYWORDS",
    "CRITICAL_KEYWORDS",
    "HEAVY_KEYWORDS",
    "LIGHT_KEYWORDS",
    "LONG_DESCRIPTION_CHAR_THRESHOLD",
    "estimate_tier",
]

# ---------------------------------------------------------------------------
# Tunable constants (NFR-002, BR-010).  Keyword sets are matched case-insensitively
# as substrings over the combined summary + description text.
# ---------------------------------------------------------------------------

# Length (in characters, over the combined summary + description) at or above
# which a description is considered "long" and is itself a HEAVY signal (TS-024).
# A shorter combined text is a precondition for a LIGHT demotion.
LONG_DESCRIPTION_CHAR_THRESHOLD = 400

# (2) Critical signals — security / auth / crypto / permission / migration /
# data-integrity / incident concerns escalate to CRITICAL.
CRITICAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "security",
        "vulnerability",
        "vulnerabilities",
        "exploit",
        "cve",
        "auth bypass",
        "authentication bypass",
        "authorization bypass",
        "privilege escalation",
        "crypto",
        "encryption",
        "permission",
        "data loss",
        "data corruption",
        "corruption",
        "data integrity",
        "pii",
        "incident",
        "outage",
        "breach",
        "payment",
    }
)

# (3a) Complexity keywords — inherent difficulty escalates to HEAVY.
COMPLEXITY_KEYWORDS: frozenset[str] = frozenset(
    {
        "complex",
        "algorithm",
        "algorithmic",
        "intricate",
        "non-trivial",
        "nontrivial",
    }
)

# (3b) Heavy signals — refactor / multi-service / schema / API-break /
# architectural scope escalate to HEAVY.
HEAVY_KEYWORDS: frozenset[str] = frozenset(
    {
        "refactor",
        "redesign",
        "rearchitect",
        "re-architect",
        "overhaul",
        "migrate",
        "migration",
        "multi-service",
        "multi service",
        "cross-service",
        "distributed",
        "concurrency",
        "replication",
        "schema change",
        "schema migration",
        "api break",
        "api-break",
        "breaking change",
        "backwards incompatible",
    }
)

# (4) Light signals — small / isolated / UI-copy work paired with a short
# description demotes to LIGHT.
LIGHT_KEYWORDS: frozenset[str] = frozenset(
    {
        "typo",
        "tooltip",
        "placeholder",
        "label copy",
        "ui copy",
        "copy change",
        "small isolated",
        "isolated tweak",
        "rename a label",
        "wording",
        "cosmetic",
    }
)


def _matches(text: str, keywords: frozenset[str]) -> list[str]:
    """Return the sorted keywords from ``keywords`` present in ``text``.

    ``text`` is expected to already be lower-cased.  Results are sorted so the
    reasons are deterministic regardless of set iteration order (TS-019).
    """
    return sorted(keyword for keyword in keywords if keyword in text)


def estimate_tier(summary: str, description: str = "") -> TierEstimate:
    """Estimate the model tier for a unit of work from its free text.

    Deterministic, side-effect-free heuristic per Section 10.5.  Matching is
    case-insensitive over ``summary + "\\n" + description``.  The returned
    :class:`TierEstimate` always carries a non-empty ``reasons`` list, including
    for baseline and empty / whitespace-only input.
    """
    combined = f"{summary}\n{description}"
    text = combined.lower()
    stripped = combined.strip()

    # (1) Baseline STANDARD, always with a baseline reason.
    if not stripped:
        return TierEstimate(
            tier=ModelTier.STANDARD,
            reasons=["Empty input; defaulting to the standard baseline tier."],
        )

    reasons: list[str] = ["No overriding signal detected; using the standard baseline tier."]

    # (2) Critical signals take precedence over everything else.
    critical_hits = _matches(text, CRITICAL_KEYWORDS)
    if critical_hits:
        return TierEstimate(
            tier=ModelTier.CRITICAL,
            reasons=[f"Critical signal(s) detected: {', '.join(critical_hits)}."],
        )

    # (3) Heavy signals: complexity keywords, architectural signals, or a long
    # description.
    heavy_reasons: list[str] = []
    complexity_hits = _matches(text, COMPLEXITY_KEYWORDS)
    if complexity_hits:
        heavy_reasons.append(f"Complexity keyword(s) detected: {', '.join(complexity_hits)}.")
    heavy_hits = _matches(text, HEAVY_KEYWORDS)
    if heavy_hits:
        heavy_reasons.append(f"Heavy signal(s) detected: {', '.join(heavy_hits)}.")
    if len(stripped) >= LONG_DESCRIPTION_CHAR_THRESHOLD:
        heavy_reasons.append(
            f"Long description ({len(stripped)} chars >= "
            f"{LONG_DESCRIPTION_CHAR_THRESHOLD}) indicates substantial scope."
        )
    if heavy_reasons:
        return TierEstimate(tier=ModelTier.HEAVY, reasons=heavy_reasons)

    # (4) Light demotion: small / isolated / UI-copy signals paired with a short
    # description.
    light_hits = _matches(text, LIGHT_KEYWORDS)
    if light_hits and len(stripped) < LONG_DESCRIPTION_CHAR_THRESHOLD:
        return TierEstimate(
            tier=ModelTier.LIGHT,
            reasons=[
                f"Small / isolated / UI-copy signal(s) detected: {', '.join(light_hits)}.",
                "Short description with only low-risk signals; demoting to the light tier.",
            ],
        )

    # (5) Baseline STANDARD with the always-present baseline reason.
    return TierEstimate(tier=ModelTier.STANDARD, reasons=reasons)
