"""Tests for normalized, checkpoint-compatible work resolution state."""

from forge.workflow.base import BaseState
from forge.workflow.bug.state import create_initial_bug_state
from forge.workflow.feature.state import create_initial_feature_state
from forge.workflow.task_takeover.state import create_initial_task_takeover_state


def test_normalized_fields_are_optional_for_legacy_checkpoints() -> None:
    """Old checkpoints need not contain fields added for work resolution."""
    optional = BaseState.__optional_keys__

    assert "artifacts" in optional
    assert "work_units" in optional
    assert "current_work_unit_id" in optional
    assert "work_resolution" in optional


def test_workflow_initial_states_have_independent_normalized_defaults() -> None:
    factories = (
        create_initial_feature_state,
        create_initial_bug_state,
        create_initial_task_takeover_state,
    )

    for factory in factories:
        first = factory("AISOS-1")
        second = factory("AISOS-2")

        assert first["artifacts"] == []
        assert first["work_units"] == []
        assert first["current_work_unit_id"] is None
        assert first["work_resolution"] == {}

        first["artifacts"].append({"id": "AISOS-1", "kind": "task"})
        first["work_units"].append({"id": "task:AISOS-1", "kind": "jira_task"})
        first["work_resolution"]["source"] = "task"

        assert second["artifacts"] == []
        assert second["work_units"] == []
        assert second["work_resolution"] == {}


def test_normalized_defaults_can_be_restored_from_checkpoint_values() -> None:
    artifacts = [{"id": "AISOS-7", "kind": "task", "source": "AISOS-7"}]
    work_units = [
        {
            "id": "task:AISOS-7",
            "kind": "jira_task",
            "key": "AISOS-7",
            "repository": "forge-sdlc/forge",
            "status": "pending",
            "source_artifact_ids": ["AISOS-7"],
        }
    ]

    state = create_initial_feature_state(
        "AISOS-7",
        artifacts=artifacts,
        work_units=work_units,
        current_work_unit_id="task:AISOS-7",
        work_resolution={"source": "task"},
    )

    assert state["artifacts"] == artifacts
    assert state["work_units"] == work_units
    assert state["current_work_unit_id"] == "task:AISOS-7"
    assert state["work_resolution"] == {"source": "task"}
