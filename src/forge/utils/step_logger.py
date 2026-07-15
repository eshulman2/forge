"""Step logging utilities for Forge workflow context validation.

Provides utilities for validating and handling workflow context values
during step logging operations.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Placeholder for unavailable context values
PLACEHOLDER_UNAVAILABLE: str = "<unavailable>"


@dataclass
class ValidationResult:
    """Result of context validation.

    Attributes:
        is_valid: True if all context values are present, False otherwise.
        warnings: List of warning messages for missing context values.
    """

    is_valid: bool
    warnings: list[str] = field(default_factory=list)


def validate_context(
    task_name: str | None,
    feature_id: str | None,
    task_id: str | None,
) -> ValidationResult:
    """Validate that all required context values are present.

    Checks each context value and generates warning messages for any
    that are missing (None or empty).

    Args:
        task_name: The name of the current task.
        feature_id: The feature identifier.
        task_id: The task identifier.

    Returns:
        ValidationResult with is_valid=True and empty warnings if all
        values are present, or is_valid=False with specific warning
        messages for each missing field.
    """
    warnings: list[str] = []

    if not task_name:
        warnings.append(f"Task name is unavailable, using {PLACEHOLDER_UNAVAILABLE!r}")

    if not feature_id:
        warnings.append(f"Feature ID is unavailable, using {PLACEHOLDER_UNAVAILABLE!r}")

    if not task_id:
        warnings.append(f"Task ID is unavailable, using {PLACEHOLDER_UNAVAILABLE!r}")

    is_valid = len(warnings) == 0

    return ValidationResult(is_valid=is_valid, warnings=warnings)
