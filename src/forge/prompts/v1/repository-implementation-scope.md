## Repository Execution Scope

Current repository: `{repository}`
Mounted workspace: `{workspace_path}`

The mounted workspace contains the repository you are responsible for in this run. Treat repository assignments in the plan as hard scope boundaries.

Implement and validate only the work that belongs to `{repository}`. Do not search for, create, or modify files assigned to other repositories. Do not implement, simulate, or create placeholder files for that work, and do not treat its absence as unfinished work. Those repositories are handled in separate mounted workspaces. Completion for this run is evaluated only against the current repository's scope.
