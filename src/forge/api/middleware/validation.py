"""Webhook payload validation middleware."""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when webhook payload validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


class WebhookSource(StrEnum):
    """Supported webhook sources."""

    JIRA = "jira"
    GITHUB = "github"


@dataclass
class ValidationResult:
    """Result of webhook payload validation."""

    is_valid: bool
    error_message: str | None = None
    error_field: str | None = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def validate_jira_payload(payload: dict[str, Any]) -> ValidationResult:
    """Validate a Jira webhook payload.

    Args:
        payload: Raw Jira webhook payload.

    Returns:
        ValidationResult indicating validity.
    """
    warnings = []

    # Check for required top-level fields
    if "webhookEvent" not in payload:
        return ValidationResult(
            is_valid=False,
            error_message="Missing required field: webhookEvent",
            error_field="webhookEvent",
        )

    # Check for issue data
    issue = payload.get("issue")
    if issue is None:
        # Some events (like sprint events) may not have issue
        event_type = payload.get("webhookEvent", "")
        if not event_type.startswith("sprint_"):
            warnings.append("No issue data in payload - may be non-issue event")

    # Validate issue structure if present
    if issue:
        if "key" not in issue:
            return ValidationResult(
                is_valid=False,
                error_message="Issue missing key field",
                error_field="issue.key",
            )

        fields = issue.get("fields")
        if not fields:
            warnings.append("Issue has no fields - limited data available")

    # Check for user data
    if "user" not in payload:
        warnings.append("No user data in payload")

    return ValidationResult(is_valid=True, warnings=warnings)


def validate_github_payload(
    payload: dict[str, Any],
    event_type: str,
) -> ValidationResult:
    """Validate a GitHub webhook payload.

    Args:
        payload: Raw GitHub webhook payload.
        event_type: Event type from X-GitHub-Event header.

    Returns:
        ValidationResult indicating validity.
    """
    warnings = []

    # Check for repository data (some events like ping may not have it)
    if "repository" not in payload and event_type != "ping":
        warnings.append("No repository data in payload")

    # Validate based on event type
    if event_type == "pull_request":
        if "pull_request" not in payload:
            return ValidationResult(
                is_valid=False,
                error_message="Missing pull_request data for pull_request event",
                error_field="pull_request",
            )

        pr = payload["pull_request"]
        if "number" not in pr:
            return ValidationResult(
                is_valid=False,
                error_message="Pull request missing number",
                error_field="pull_request.number",
            )

    elif event_type == "check_run":
        if "check_run" not in payload:
            return ValidationResult(
                is_valid=False,
                error_message="Missing check_run data for check_run event",
                error_field="check_run",
            )

    elif event_type == "check_suite":
        if "check_suite" not in payload:
            return ValidationResult(
                is_valid=False,
                error_message="Missing check_suite data for check_suite event",
                error_field="check_suite",
            )

    elif event_type in ("pull_request_review", "pull_request_review_comment"):
        if "pull_request" not in payload:
            return ValidationResult(
                is_valid=False,
                error_message="Missing pull_request data for review event",
                error_field="pull_request",
            )
        required_key = "review" if event_type == "pull_request_review" else "comment"
        if required_key not in payload:
            return ValidationResult(
                is_valid=False,
                error_message=f"Missing {required_key} data for review event",
                error_field=required_key,
            )

    # Check for sender
    if "sender" not in payload and event_type != "ping":
        warnings.append("No sender data in payload")

    return ValidationResult(is_valid=True, warnings=warnings)


def validate_webhook_payload(
    payload: dict[str, Any],
    source: WebhookSource,
    event_type: str | None = None,
) -> ValidationResult:
    """Validate a webhook payload based on its source.

    Args:
        payload: Raw webhook payload.
        source: Webhook source (jira or github).
        event_type: Event type (required for GitHub).

    Returns:
        ValidationResult indicating validity.
    """
    if source == WebhookSource.JIRA:
        return validate_jira_payload(payload)
    elif source == WebhookSource.GITHUB:
        if event_type is None:
            return ValidationResult(
                is_valid=False,
                error_message="Event type required for GitHub webhooks",
            )
        return validate_github_payload(payload, event_type)
    else:
        return ValidationResult(
            is_valid=False,
            error_message=f"Unknown webhook source: {source}",
        )
