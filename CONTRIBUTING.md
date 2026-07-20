# Contributing to Forge

Thanks for your interest. This document explains what kind of contributions Forge welcomes and how to make them.

## Have an idea or need help?

Open a [GitHub issue](https://github.com/Forge-sdlc/forge/issues). Issues are the right place for feature ideas, questions, bug reports, and anything else you want to discuss before writing code. If your idea is larger in scope — a new workflow type, a significant change to the pipeline, a new integration — you can also submit a proposal following the format in `proposals/TEMPLATE.md`. Proposals give everyone a chance to read, comment, and align before implementation starts.

The point is to work on things together. An early conversation usually leads to a better outcome than a PR that surprises everyone.

## The fastest way to contribute: write a skill set

If your team uses Forge and has customized how it behaves for your stack — your CI failure categories, your PRD format, your implementation conventions — that knowledge is worth sharing.

**A skill set is a directory under `skills/` named after your Jira project key (lowercase):**

```
skills/
└── myteam/
    ├── analyze-ci/
    │   └── SKILL.md       ← your CI failure categories and tooling
    └── generate-prd/
        ├── SKILL.md       ← your PRD process
        └── prd-template.md
```

You only need to include the skills you actually changed. Any skill you don't provide falls back to `skills/default/` automatically.

See [`skills/README.md`](skills/README.md) for the authoring guide — what belongs in a skill, what belongs in a system prompt, and the quality bar for defaults.

### To contribute a skill set

1. Fork the repo
2. Create `skills/{your-project-key}/` with your customized skills
3. Make sure your skills are genuinely stack-specific (not a copy of the default)
4. Submit a PR with a short description of your stack and what you changed

We'll review for quality and clarity, not for agreement with your choices — the point is that your conventions work for your team.

## Other ways to contribute

### Bug fixes

If something in the core workflow is broken, a focused fix with a test is always welcome. Keep the scope tight — a bug fix should fix the bug and nothing else.

### Default skill improvements

The skills in `skills/default/` should work for any software project regardless of stack. If you find something in a default skill that's OpenShift-specific, Java-specific, or otherwise not genuinely general — that's a bug. Fix it and submit a PR.

If you want to improve a default skill's quality (better structure, clearer instructions, a missing edge case) — open an issue first to discuss, especially for significant changes that affect everyone.

### New workflow ideas

Open a [GitHub issue](https://github.com/Forge-sdlc/forge/issues) or submit a proposal in `proposals/` before writing any code. An early conversation saves everyone time and means the implementation is more likely to land.

### Documentation

Typos, clarifications, and missing explanations are always welcome.

## Development setup

See the [Developer Guide](docs/developer-guide.md) for the full local setup, including Redis, the API server, the worker, payload-based testing, and debugging tools.

Before submitting a PR, make sure these pass:

```bash
make lint
make test-pr
make test-integration  # requires Docker/Podman, or FORGE_TEST_REDIS_URL
make test-e2e
```

The required CI gates run unit coverage, API contract tests, workflow flow tests,
Redis-backed integration tests, deterministic E2E smoke tests, and a production
container build independently. Unit coverage must remain at or above 60%; the
report includes branch coverage and is uploaded as a CI artifact.

## Pull request guidelines

- **One thing per PR.** A skill set, a bug fix, or a doc improvement — not all three.
- **Tests for code changes.** New logic needs tests. Skills don't need tests, but the resolver does.
- **No unrelated cleanup.** If you notice something off while working on your change, open a separate issue.
- **Short description.** What does this change and why? One paragraph is enough.

## Questions

Open a [GitHub issue](https://github.com/Forge-sdlc/forge/issues) — for "how do I" questions, sharing what your team built, or early feedback before you start writing code.
