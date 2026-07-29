"""GitHub webhook payload parsing and validation."""

import logging
import re
from dataclasses import dataclass
from typing import Any

from forge.models.events import EventSource, WebhookEvent

logger = logging.getLogger(__name__)

# Pattern to extract Jira ticket keys from PR titles/branches
TICKET_PATTERN = re.compile(r"([A-Z][A-Z0-9]+-\d+)", re.IGNORECASE)


@dataclass
class GitHubWebhookData:
    """Parsed data from a GitHub webhook payload."""

    event_id: str
    event_type: str
    action: str
    repo_full_name: str
    ticket_key: str | None
    pr_number: int | None
    pr_url: str | None
    pr_state: str | None
    branch_name: str | None
    commit_sha: str | None
    check_status: str | None
    check_conclusion: str | None
    sender_login: str
    raw_payload: dict[str, Any]


def parse_github_webhook(
    payload: dict[str, Any],
    event_type: str,
    event_id: str,
) -> GitHubWebhookData:
    """Parse a GitHub webhook payload into structured data.

    Args:
        payload: Raw webhook payload from GitHub.
        event_type: Event type from X-GitHub-Event header.
        event_id: Unique event identifier from X-GitHub-Delivery header.

    Returns:
        Parsed GitHubWebhookData.
    """
    action = payload.get("action", "")
    repo = payload.get("repository", {})
    sender = payload.get("sender", {})

    # Common fields
    repo_full_name = repo.get("full_name", "")
    sender_login = sender.get("login", "")

    # Extract ticket key from various sources
    ticket_key = None
    pr_number = None
    pr_url = None
    pr_state = None
    branch_name = None
    commit_sha = None
    check_status = None
    check_conclusion = None

    # Handle pull_request events
    if event_type == "pull_request":
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        pr_url = pr.get("html_url")
        pr_state = pr.get("state")
        branch_name = pr.get("head", {}).get("ref", "")

        # Try to extract ticket from PR title first, then branch name
        pr_title = pr.get("title", "")
        ticket_key = _extract_ticket_key(pr_title) or _extract_ticket_key(branch_name)

    # Handle check_run events (CI status)
    elif event_type == "check_run":
        check_run = payload.get("check_run", {})
        check_status = check_run.get("status")
        check_conclusion = check_run.get("conclusion")
        commit_sha = check_run.get("head_sha")

        # Get ticket from associated PRs
        pull_requests = check_run.get("pull_requests", [])
        if pull_requests:
            pr = pull_requests[0]
            pr_number = pr.get("number")
            pr_url = pr.get("url")
            branch_name = pr.get("head", {}).get("ref", "")
            ticket_key = _extract_ticket_key(branch_name)

    # Handle check_suite events
    elif event_type == "check_suite":
        check_suite = payload.get("check_suite", {})
        check_status = check_suite.get("status")
        check_conclusion = check_suite.get("conclusion")
        commit_sha = check_suite.get("head_sha")
        branch_name = check_suite.get("head_branch", "")
        ticket_key = _extract_ticket_key(branch_name)

        # Get ticket from associated PRs
        pull_requests = check_suite.get("pull_requests", [])
        if pull_requests:
            pr = pull_requests[0]
            pr_number = pr.get("number")

    # Handle pull request review submissions and inline thread replies
    elif event_type in ("pull_request_review", "pull_request_review_comment"):
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        pr_url = pr.get("html_url")
        pr_state = pr.get("state")
        branch_name = pr.get("head", {}).get("ref", "")
        pr_title = pr.get("title", "")
        ticket_key = _extract_ticket_key(pr_title) or _extract_ticket_key(branch_name)

    # Handle push events
    elif event_type == "push":
        branch_name = payload.get("ref", "").replace("refs/heads/", "")
        commit_sha = payload.get("after")
        ticket_key = _extract_ticket_key(branch_name)

    # Handle issue_comment events (PR comments)
    elif event_type == "issue_comment":
        issue = payload.get("issue", {})
        # Check if this is a PR (has pull_request field)
        if issue.get("pull_request"):
            pr_number = issue.get("number")
            pr_url = issue.get("html_url")
            pr_title = issue.get("title", "")
            ticket_key = _extract_ticket_key(pr_title)

    return GitHubWebhookData(
        event_id=event_id,
        event_type=event_type,
        action=action,
        repo_full_name=repo_full_name,
        ticket_key=ticket_key,
        pr_number=pr_number,
        pr_url=pr_url,
        pr_state=pr_state,
        branch_name=branch_name,
        commit_sha=commit_sha,
        check_status=check_status,
        check_conclusion=check_conclusion,
        sender_login=sender_login,
        raw_payload=payload,
    )


def create_github_webhook_event(data: GitHubWebhookData) -> WebhookEvent:
    """Create a WebhookEvent from parsed GitHub webhook data.

    Args:
        data: Parsed GitHub webhook data.

    Returns:
        WebhookEvent ready for queue publishing.
    """
    return WebhookEvent(
        event_id=data.event_id,
        source=EventSource.GITHUB,
        event_type=f"{data.event_type}:{data.action}" if data.action else data.event_type,
        ticket_key=data.ticket_key or "",
        payload=data.raw_payload,
    )


def _extract_ticket_key(text: str) -> str | None:
    """Extract Jira ticket key from text.

    Args:
        text: Text that may contain a ticket key.

    Returns:
        First ticket key found, or None.
    """
    if not text:
        return None

    match = TICKET_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    return None


def is_ci_success(data: GitHubWebhookData) -> bool:
    """Check if the webhook indicates CI success.

    Args:
        data: Parsed webhook data.

    Returns:
        True if CI has passed.
    """
    return data.check_status == "completed" and data.check_conclusion == "success"


def is_ci_failure(data: GitHubWebhookData) -> bool:
    """Check if the webhook indicates CI failure.

    Args:
        data: Parsed webhook data.

    Returns:
        True if CI has failed.
    """
    return data.check_status == "completed" and data.check_conclusion in (
        "failure",
        "cancelled",
        "timed_out",
    )


def is_pr_merged(data: GitHubWebhookData) -> bool:
    """Check if the webhook indicates a PR was merged.

    Args:
        data: Parsed webhook data.

    Returns:
        True if PR was merged.
    """
    return (
        data.event_type == "pull_request"
        and data.action == "closed"
        and data.raw_payload.get("pull_request", {}).get("merged", False)
    )


def is_pr_review_approved(data: GitHubWebhookData) -> bool:
    """Check if the webhook indicates PR review approval.

    Args:
        data: Parsed webhook data.

    Returns:
        True if PR was approved.
    """
    return (
        data.event_type == "pull_request_review"
        and data.action == "submitted"
        and data.raw_payload.get("review", {}).get("state") == "approved"
    )


def is_pr_review_changes_requested(data: GitHubWebhookData) -> bool:
    """Check if the webhook indicates changes were requested.

    Args:
        data: Parsed webhook data.

    Returns:
        True if changes were requested.
    """
    return (
        data.event_type == "pull_request_review"
        and data.action == "submitted"
        and data.raw_payload.get("review", {}).get("state") in ("changes_requested", "commented")
    )
