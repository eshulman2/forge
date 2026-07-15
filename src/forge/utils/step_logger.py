"""Step logging utilities for Forge workflow context validation.

Provides utilities for validating and handling workflow context values
during step logging operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

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


def log_step_start(
    task_name: str | None,
    feature_id: str | None,
    task_id: str | None,
) -> None:
    """Log the start of a workflow step with context validation.

    Validates the provided context values and logs any warnings for missing
    values at WARNING level. Then emits an INFO log message indicating the
    step is starting with a human-readable ISO 8601 timestamp.

    Args:
        task_name: The name of the current task.
        feature_id: The feature identifier.
        task_id: The task identifier.
    """
    # Validate context and log any warnings
    validation = validate_context(task_name, feature_id, task_id)
    for warning in validation.warnings:
        logger.warning(warning)

    # Use placeholder for missing values
    effective_task_name = task_name if task_name else PLACEHOLDER_UNAVAILABLE
    effective_feature_id = feature_id if feature_id else PLACEHOLDER_UNAVAILABLE
    effective_task_id = task_id if task_id else PLACEHOLDER_UNAVAILABLE

    # Generate ISO 8601 timestamp
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Emit INFO log with structured fields
    logger.info(
        f"[{timestamp}] Step starting: task_name={effective_task_name}, "
        f"feature_id={effective_feature_id}, task_id={effective_task_id}",
        extra={
            "timestamp": timestamp,
            "event": "step_start",
            "task_name": effective_task_name,
            "feature_id": effective_feature_id,
            "task_id": effective_task_id,
        },
    )


def log_step_end(
    task_name: str | None,
    feature_id: str | None,
    task_id: str | None,
) -> None:
    """Log the end of a workflow step with context validation.

    Validates the provided context values and logs any warnings for missing
    values at WARNING level. Then emits an INFO log message indicating the
    step has ended with a human-readable ISO 8601 timestamp.

    Args:
        task_name: The name of the current task.
        feature_id: The feature identifier.
        task_id: The task identifier.
    """
    # Validate context and log any warnings
    validation = validate_context(task_name, feature_id, task_id)
    for warning in validation.warnings:
        logger.warning(warning)

    # Use placeholder for missing values
    effective_task_name = task_name if task_name else PLACEHOLDER_UNAVAILABLE
    effective_feature_id = feature_id if feature_id else PLACEHOLDER_UNAVAILABLE
    effective_task_id = task_id if task_id else PLACEHOLDER_UNAVAILABLE

    # Generate ISO 8601 timestamp
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Emit INFO log with structured fields
    logger.info(
        f"[{timestamp}] Step ended: task_name={effective_task_name}, "
        f"feature_id={effective_feature_id}, task_id={effective_task_id}",
        extra={
            "timestamp": timestamp,
            "event": "step_end",
            "task_name": effective_task_name,
            "feature_id": effective_feature_id,
            "task_id": effective_task_id,
        },
    )
