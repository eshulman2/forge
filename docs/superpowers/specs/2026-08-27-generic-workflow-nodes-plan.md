# Generic workflow nodes: migration plan

## Goal

Make Forge workflows composable from capabilities and normalized state instead of ticket-type
specific node implementations. YAML continues to select only allowlisted nodes and routers; it does
not contain Python, prompts, expressions, or arbitrary commands.

The target is not one universal node. The target is a small set of nodes with stable contracts:

```text
resolve_repositories -> generate_artifact -> review_artifact -> advance_work
    -> setup_workspace -> implement_work -> validate_changes -> publish_changes
    -> wait_for_checks -> advance_work
```

Nodes that perform materially different operations remain separate. Configuration selects an
allowlisted policy, never executable behavior.

## Proposed normalized state

The existing `artifacts`, `work_units`, `current_work_unit_id`, `work_resolution`, and
`capabilities` fields are the foundation. Add the following optional checkpoint-safe structures to
`BaseState` and integration mixins:

```python
class RepositoryRef(TypedDict, total=False):
    name: str                     # owner/repository
    source: str                   # task label, epic label, project config, or event
    status: str                   # pending, active, completed, blocked
    work_unit_ids: list[str]


class ValidationResult(TypedDict, total=False):
    id: str
    repository: str
    work_unit_id: str | None
    kind: str                     # lint, test, build, qualitative_review
    status: str                   # passed, failed, skipped
    summary: str
    evidence: dict[str, Any]


class PublicationRef(TypedDict, total=False):
    repository: str
    commit_sha: str | None
    branch: str | None
    pr_url: str | None
    status: str                   # no_changes, pushed, pr_open, merged, failed


class BaseState(TypedDict, total=False):
    repositories: list[RepositoryRef]
    current_repository: str | None
    artifacts: list[ArtifactRef]
    work_units: list[WorkUnit]
    current_work_unit_id: str | None
    validations: list[ValidationResult]
    publications: list[PublicationRef]
    capabilities: dict[str, bool]
    node_outcome: str | None
```

Compatibility aliases remain during migration:

| Normalized field | Existing fields retained temporarily |
| --- | --- |
| `repositories` | `repos_to_process`, `repos_completed`, `tasks_by_repo` |
| `current_repository` | `current_repo` |
| `work_units` | `task_keys`, `current_task_key`, `implemented_tasks` |
| `validations` | `task_execution_results`, `ai_review_results`, `ci_status` |
| `publications` | `commit_info`, `pr_urls`, `pull_requests`, `current_pr_url` |

Adapters should write both representations until built-in graphs and old checkpoints no longer
depend on the legacy fields. Reads prefer normalized state and fall back to legacy fields.

State collections are append-or-upsert by stable identity. A later repository or retry must not
erase previous artifacts, completed work units, validations, or publications.

## Generic node contracts

### 1. `resolve_repositories`

Purpose: produce the ordered repository scope before workspace or implementation operations.

Inputs, in precedence order:

1. repository on the selected Task/work unit;
2. `repo:*` labels on Tasks and repository Epics;
3. existing normalized repository state;
4. root-ticket labels;
5. Jira project repository configuration.

Outputs:

- upserts `repositories`;
- sets `current_repository` and compatibility fields;
- sets `capabilities.repositories`;
- records source/provenance and blocks on conflicting assignments.

Existing code affected: repository inference in `task_router`, `setup_workspace`, task-takeover
planning, feature planning nodes, and bug planning should move behind this resolver. Those nodes may
continue adding repository labels, but should not independently choose a repository.

### 2. `generate_artifact`

Purpose: share generation mechanics while preserving artifact-specific policies.

The workflow step references an allowlisted generation policy such as `prd`, `spec`, `feature_plan`,
or `rca`. The policy defines the prompt, required inputs, output parser, Jira representation,
approval policy, and whether a proposal PR is needed.

Outputs:

- upserts an `ArtifactRef` with content digest, approval state, repository scope, and provenance;
- mirrors content to `prd_content`, `spec_content`, `plan_content`, or `rca_content` while compatible;
- preserves workflow and repository labels on created or updated Jira issues;
- sets `node_outcome` to `generated`, `needs_input`, or `failed`.

Existing nodes initially become thin wrappers: `generate_prd`, `generate_spec`, `plan_bug_fix`,
`analyze_bug`, and task-takeover `generate_plan`. Epic/task decomposition remains separate because
it creates work hierarchy rather than one document.

### 3. `review_artifact`

Purpose: provide one approval/revision state machine for planning artifacts.

Inputs: artifact ID or kind, an allowlisted rubric, review mode (`human`, `agent`, or both), and
retry/escalation policy.

Outputs:

- updates `ArtifactRef.approved` and provenance;
- records structured review history;
- sets `node_outcome` to `approved`, `revise`, `question`, or `escalate`.

Existing PRD/spec/plan gates retain their Jira-facing wording through wrappers. Ticket-specific
routers can then converge on a generic `route_node_outcome` router.

### 4. `advance_work`

Purpose: select the next repository-scoped unit without embedding loops in ticket-specific graphs.

Resolution order remains Task first, then repository Epic plan, general plan, spec/RCA, PRD, and
root ticket. It skips completed units, selects the next repository when appropriate, and never falls
back to a broader artifact while known Tasks remain unfinished.

Outputs:

- upserts `work_units` and `work_resolution`;
- sets `current_work_unit_id` and `current_repository`;
- sets `node_outcome` to `implement`, `next_repository`, `complete`, or `blocked`.

The current resolver inside `implement_work` can be extracted into this node later. During the first
phase, `implement_work` remains capable of resolving input itself for checkpoint compatibility.

### 5. `validate_changes`

Purpose: converge feature local review, bug local review, task qualitative review, and repository
build/test checks without pretending their rubrics are identical.

An allowlisted validation profile chooses checks and rubric. Repository-defined commands may be
read from trusted Forge project configuration, not workflow YAML.

Outputs:

- appends/upserts `validations`;
- records whether code exists and whether required checks passed;
- sets `capabilities.validated` and `node_outcome` (`passed`, `fix`, or `escalate`).

Existing `local_review_changes` and `run_qualitative_review` become wrappers. CI validation remains
external and belongs to `wait_for_checks`.

### 6. `publish_changes`

Purpose: own the transition from workspace changes to durable commit, push, and optional PR.

Behavior:

- no diff: records `no_changes` and routes without trying to create a PR;
- diff present: commits and pushes idempotently;
- PR requested: creates or reuses the repository PR;
- push/PR failure: records retryable persistence state before returning.

Outputs update `publications`, `capabilities.code_changes`, and `capabilities.pull_request`. Existing
fields continue to be mirrored. `create_pr` becomes a wrapper configured with `require_pr=true`.
Implementation may continue pushing for recovery safety initially; publication becomes the sole
owner only after checkpoints can resume safely between execution and push.

### 7. `wait_for_checks`

Purpose: unify CI preconditions, waiting, evaluation, retry, timeout, and “no PR” handling.

Behavior is driven by explicit capabilities:

- `pull_request=false`: skip only when the workflow marks CI optional; otherwise block;
- PR exists but no checks were scheduled: wait until timeout, then apply policy;
- checks failed: return `fix` while attempts remain, otherwise `escalate`;
- checks passed or explicitly skipped: return `passed`.

Existing `ci_evaluator` and `attempt_ci_fix` become wrappers or branches around this node.

## Effect on built-in workflows

| Workflow | First migration | Target shape | User-visible change |
| --- | --- | --- | --- |
| Feature | task router and implementation loop | artifacts → advance → implement → validate → publish → CI | Task-based behavior stays first; task breakdown becomes optional |
| Bug | repository resolution and bug implementation wrapper | RCA/plan → advance → implement → validate → publish → CI | A bug Task and an artifact-only fix use the same execution path |
| Task takeover | planning/execution wrapper | resolve → optional plan → advance → implement → validate → publish | Root Task stays the most specific work unit |
| Declarative | add generic nodes to common catalog | compose capability nodes directly | More sequences become possible without hidden stages |

Built-in workflows should migrate by wrapper first, graph replacement second. This keeps node names,
pause/resume behavior, Jira comments, and saved checkpoints stable during rollout.

## Example declarative workflow

The desired “PRD → spec → plan → implementation without task breakdown” workflow would eventually
look like this:

```yaml
apiVersion: forge/v1
kind: Workflow
metadata:
  name: artifact-driven-feature
  revision: 1
spec:
  state: feature
  entry: generate_prd
  steps:
    generate_prd:
      next: prd_approval_gate
    prd_approval_gate:
      route: route_prd_approval
      branches:
        generate_spec: generate_spec
        regenerate_prd: generate_prd
        answer_question: answer_question
        __end__: __end__
    answer_question:
      next: prd_approval_gate
    generate_spec:
      next: spec_approval_gate
    spec_approval_gate:
      route: route_spec_approval
      branches:
        generate_tasks: generate_plan
        regenerate_spec: generate_spec
        answer_question: answer_question
        __end__: __end__
    generate_plan:
      next: resolve_repositories
    resolve_repositories:
      next: advance_work
    advance_work:
      route: route_node_outcome
      branches:
        implement: setup_workspace
        next_repository: setup_workspace
        complete: __end__
        blocked: escalate_blocked
    setup_workspace:
      next: implement_work
    implement_work:
      next: validate_changes
    validate_changes:
      route: route_node_outcome
      branches:
        passed: publish_changes
        fix: implement_work
        escalate: escalate_blocked
    publish_changes:
      route: route_node_outcome
      branches:
        pr_open: wait_for_checks
        no_changes: advance_work
        failed: escalate_blocked
    wait_for_checks:
      route: route_node_outcome
      branches:
        passed: advance_work
        fix: implement_work
        escalate: escalate_blocked
```

This is the target format, not valid against the current catalog: `generate_plan`,
`resolve_repositories`, `advance_work`, `validate_changes`, `publish_changes`, `wait_for_checks`, and
`route_node_outcome` must first be implemented and allowlisted. Step parameters should be introduced
only with a schema that references named policies.

## Existing-node migration map

| Current node or concern | Generic destination | Migration approach |
| --- | --- | --- |
| `route_tasks_by_repo`, workspace repo fallback | `resolve_repositories`, `advance_work` | extract resolver; retain wrappers |
| `implement_task`, bug `_implement_task_bug`, `execute_task_changes` | `implement_work` | share resolver/execution engine, then wrappers |
| `generate_prd`, `generate_spec`, plan/RCA generators | `generate_artifact` | extract policy and persistence adapters |
| PRD/spec/plan approval gates | `review_artifact` | preserve gate names as wrappers |
| feature/bug local review, task qualitative review | `validate_changes` | named validation profiles |
| implementation push and `create_pr` | `publish_changes` | staged handoff to preserve crash recovery |
| `ci_evaluator`, `attempt_ci_fix` | `wait_for_checks` | normalize check state and outcomes |
| workflow-specific route helpers | `route_node_outcome` | migrate after outcome values stabilize |

## Preconditions and invariants

Each node gets a declarative `NodeContract`:

| Node | Required capabilities | Important invariant |
| --- | --- | --- |
| `resolve_repositories` | planning context or root ticket | conflicts block; no guessed repository |
| `generate_artifact` | policy-specific inputs | output is digested and provenance recorded |
| `review_artifact` | selected artifact | only the selected digest is approved |
| `advance_work` | repositories and planning context | pending Tasks prevent broader fallback |
| `setup_workspace` | repositories | workspace identity matches repository |
| `implement_work` | repository, workspace, planning context | changes remain repository-scoped |
| `validate_changes` | workspace, implementation result | evidence belongs to current work unit |
| `publish_changes` | workspace and repository | no PR without a durable diff/branch |
| `wait_for_checks` | explicit PR capability | never waits for a PR that cannot exist |

All external side-effect nodes must be idempotent by stable identifiers. Preconditions and outcomes
are persisted before routing so checkpoint resume does not infer them from transient files.

## Delivery sequence

1. **State adapters:** add repositories, validations, publications, `node_outcome`, and compatibility
   helpers; add checkpoint round-trip and old-state tests.
2. **Repository/work loop:** implement `resolve_repositories`, extract `advance_work`, and migrate
   task routing wrappers. This removes the largest workflow-specific branching.
3. **Validation:** introduce named validation profiles and migrate local/qualitative review wrappers.
4. **Publication:** normalize diff/commit/push/PR state and make no-code behavior explicit.
5. **CI:** implement `wait_for_checks` with PR/no-PR and no-check timeout policies.
6. **Artifact lifecycle:** extract generator/reviewer engines behind existing PRD/spec/plan/RCA nodes.
7. **Graph migration:** simplify built-in graphs only after parity tests and live canaries succeed.

Each phase should be a separate PR. Generic nodes enter the declarative allowlist only after their
contracts, idempotency, resume behavior, and profile-specific integration tests pass.

## Test and rollout plan

- Unit-test every resolver precedence, conflict, absent capability, retry, and no-op case.
- Contract-test normalized writes plus legacy-field mirroring for feature, bug, and task takeover.
- Compile representative YAML graphs and verify unreachable branches/cycles remain rejected.
- Resume fixtures created from pre-migration checkpoints at every wrapper boundary.
- Run parity tests: old built-in node versus wrapper over generic engine using the same mocked inputs.
- Deploy behind per-node feature flags; keep built-in graph topology unchanged initially.
- Canary in a disposable Jira project workflow before enabling a generic node broadly.
- Record resolution source, selected policy, state digest, outcome, and side-effect identifier in
  structured logs for rollback diagnosis.

## Main risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Generic behavior loses workflow semantics | named policies and thin workflow wrappers |
| Old checkpoints cannot resume | optional fields, dual reads/writes, revision migrations, fixtures |
| State becomes contradictory | normalized state is authoritative; compatibility fields are derived |
| Duplicate Jira/commit/PR side effects | stable idempotency keys and persisted pending states |
| Workflow YAML becomes executable configuration | static node/policy allowlists; no commands or expressions |
| Wrong repository receives changes | provenance, conflict blocking, workspace identity checks |
| CI waits forever without a PR/check run | explicit PR capability, timeout, skip/block policy |
| Artifact changes after approval | approve a digest and invalidate approval when the digest changes |

## Definition of done

- Feature, Bug, and Task Takeover can execute through the same repository/work/validation/publication
  primitives without changing their default user-visible behavior.
- A declarative feature workflow can omit Task generation and implement from an approved plan, spec,
  PRD, or root ticket while still resolving a repository explicitly.
- Known Jira Tasks always outrank coarser planning artifacts.
- No-code workflows do not attempt PR creation or CI waiting.
- Old checkpoints resume, all external operations are idempotent, and every generic node has a
  precondition contract plus audit state.
