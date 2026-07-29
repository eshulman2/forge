"""Per-thread semantic triage for generated proposal reviews."""

import json
import logging
import re
from typing import Any

from forge.prompts import load_prompt

logger = logging.getLogger(__name__)

_DISPOSITIONS = {"accept", "reply", "uncertain", "ignore"}


def parse_proposal_thread_decisions(
    output: str, threads: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Parse decisions and conservatively accept missing or malformed items."""
    expected = {thread["thread_id"]: thread for thread in threads}
    match = re.search(r"\[.*\]", output, re.DOTALL)
    parsed: list[Any] = []
    if match:
        try:
            value = json.loads(match.group(0))
            if isinstance(value, list):
                parsed = value
        except json.JSONDecodeError:
            pass

    decisions: dict[str, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict) or item.get("thread_id") not in expected:
            continue
        disposition = item.get("disposition")
        if disposition not in _DISPOSITIONS:
            continue
        thread = expected[item["thread_id"]]
        comment_id = thread["comments"][-1].get("comment_id")
        decisions[item["thread_id"]] = {
            "thread_id": item["thread_id"],
            "comment_id": comment_id,
            "disposition": disposition,
            "feedback": str(item.get("feedback", "")).strip(),
            "response": str(item.get("response", "")).strip(),
            "reason": str(item.get("reason", "")).strip(),
        }

    for thread_id, thread in expected.items():
        if thread_id in decisions:
            continue
        latest = thread["comments"][-1]
        decisions[thread_id] = {
            "thread_id": thread_id,
            "comment_id": latest.get("comment_id"),
            "disposition": "uncertain",
            "feedback": latest.get("body", ""),
            "response": "",
            "reason": "Thread triage was unavailable or inconclusive",
        }
    return list(decisions.values())


async def triage_proposal_review_threads(
    *, artifact_type: str, artifact_content: str, threads: list[dict[str, Any]], ticket_key: str
) -> list[dict[str, Any]]:
    """Classify proposal review threads in one tool-free agent invocation."""
    from forge.integrations.agents.agent import ForgeAgent

    rendered_threads = json.dumps(threads, indent=2)
    prompt = load_prompt(
        "triage-proposal-review-threads",
        artifact_type=artifact_type,
        artifact_content=artifact_content,
        review_threads=rendered_threads,
    )
    try:
        output = await ForgeAgent().run_task(
            task="triage-proposal-review-threads",
            prompt=prompt,
            context={"ticket_key": ticket_key},
            include_tools=False,
        )
    except Exception as exc:
        logger.warning("Proposal thread triage failed for %s: %s", ticket_key, exc)
        output = ""
    return parse_proposal_thread_decisions(output, threads)


async def reply_to_proposal_decisions(
    *,
    repo_full_name: str,
    pr_number: int,
    decisions: list[dict[str, Any]],
    dispositions: set[str],
    default_response: str = "",
) -> None:
    """Reply to selected proposal decisions in their originating threads."""
    from forge.integrations.github.client import GitHubClient

    owner, repo = repo_full_name.split("/", 1)
    github = GitHubClient()
    try:
        for decision in decisions:
            if decision.get("disposition") not in dispositions:
                continue
            if decision.get("status") == "addressed":
                continue
            comment_id = decision.get("comment_id")
            response = decision.get("response") or default_response
            if not isinstance(comment_id, int) or not response:
                continue
            try:
                await github.reply_to_review_comment(owner, repo, pr_number, comment_id, response)
            except Exception as exc:
                logger.warning("Failed replying to proposal comment %s: %s", comment_id, exc)
    finally:
        await github.close()
