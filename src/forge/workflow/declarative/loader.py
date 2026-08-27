"""Load workflow definitions from Jira JSON values or local YAML/JSON files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from forge.workflow.declarative.models import MAX_PROPERTY_BYTES, WorkflowDefinition

MAX_YAML_DEPTH = 32
MAX_YAML_ALIASES = 32


class LimitedSafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """Safe loader with conservative nesting and alias limits."""

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._forge_depth = 0
        self._forge_aliases = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            self._forge_aliases += 1
            if self._forge_aliases > MAX_YAML_ALIASES:
                raise yaml.YAMLError(f"YAML may contain at most {MAX_YAML_ALIASES} aliases")
        self._forge_depth += 1
        if self._forge_depth > MAX_YAML_DEPTH:
            raise yaml.YAMLError(f"YAML nesting may not exceed {MAX_YAML_DEPTH} levels")
        try:
            return super().compose_node(parent, index)
        finally:
            self._forge_depth -= 1


def load_workflow_value(value: Any) -> WorkflowDefinition:
    """Validate a JSON-compatible Jira project-property value."""
    if not isinstance(value, dict):
        raise ValueError("workflow project property must be a JSON object")
    definition = WorkflowDefinition.model_validate(value)
    definition.validate_property_size()
    return definition


def load_workflow_file(path: str | Path) -> WorkflowDefinition:
    """Safely parse and validate one local YAML or JSON workflow document."""
    source = Path(path)
    raw_bytes = source.read_bytes()
    if len(raw_bytes) > MAX_PROPERTY_BYTES:
        raise ValueError(
            f"workflow file is {len(raw_bytes)} bytes; maximum is {MAX_PROPERTY_BYTES} bytes"
        )
    raw = yaml.load(raw_bytes.decode("utf-8"), Loader=LimitedSafeLoader)
    return load_workflow_value(raw)
