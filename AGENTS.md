# Repository instructions

## Scope and GitHub workflow

- For status, explanation, or review requests, inspect and report. Make changes only when requested or clearly part of the authorized task.
- Prefer `main` for new repositories. Use the existing default branch in established repositories and submit all changes to it through pull requests. Preserve existing branch protection and report any verified gaps in protection or PR enforcement.
- Change repository settings, visibility, app permissions, collaborator access, or publishing credentials only with explicit authorization.
- Associate every repository change with a GitHub issue, including code, documentation, copy, configuration, maintenance, and agent instructions. Before editing, find an issue that covers the work or create one. Reuse it for follow-up fixes within its scope.
- Start from the latest default branch on a dedicated issue branch. Prefer `<issue-number>-<short-description>`. Keep unrelated work in separate branches and pull requests, and preserve uncommitted work from other tasks.
- Use `git` for version-control operations such as fetching, branching, committing, and pushing. Make file changes in the local checkout and publish branch commits with `git push`. Use `gh` for GitHub-specific work such as managing issues, pull requests, and labels, reading review feedback, and checking CI status.
- Every PR must reference at least one existing issue in its description. Use `Closes #N` for an issue the PR completes when it targets the default branch. For partial work, use `Related to #N` and state what remains. A non-closing reference satisfies the issue requirement for partial work.
- Check applicable review feedback and CI before reporting a PR as ready. State which checks could not run and why.

## Issue types and fields

- Use GitHub's standard issue types `Bug`, `Feature`, and `Task`.
- Set one priority per issue using the native GitHub Priority field. If the field cannot be set, record the value temporarily under `## Priority` in the issue body. Use the native field as the source of truth when it is readable and set.

| Priority (highest to lowest) | Use for |
| --- | --- |
| Urgent | Release blockers and problems that prevent basic use, including critical accessibility issues |
| High | Near-term functionality, documentation, or workflow improvements |
| Medium | Follow-up polish, secondary improvements, or organization |
| Low | Optional exploration |

- Use Effort to estimate scope and uncertainty. Use `Low` for small, well-understood work, `Medium` for moderate scope or uncertainty, and `High` for broad scope or significant uncertainty.
- Set Start date to the date work actually began. Leave it blank until work starts. Set Target date only when a target has been established.
- Confirm scope, dependencies, and missing inputs before starting. When choosing work, use priority to decide what matters most and readiness to decide what can start. Pick the highest-priority actionable issue or unblock its prerequisite. Evaluate effort independently of priority and readiness.
- Preserve explicit priorities unless the repository owner authorizes a change. Record the rationale for each change and preserve completed issues' historical priorities. When triaging, audit all open issues for missing or ambiguous priorities.
- Distinguish verified configuration gaps from tooling that cannot read or set an existing field or setting. Use another authorized method when available, report what could be verified, and continue any authorized work that can proceed. Propose configuration changes or broader access only when needed for the task.

## Pull request labels and attribution

- When opening or updating a PR, apply exactly one change-type label from the repository's documented label catalog. Recheck it when scope changes, replace stale change-type labels, and verify the applied label. Report a missing catalog or label separately from a tooling limitation.
- Add a concise **AI assistance:** footer when opening a PR that Codex created or substantially implemented. Describe Codex's actual contribution and identify the authenticated account used to open the PR when verified. Include the verified Codex version and model name when available and relevant. Omit unavailable details and retain the footer when updating the PR description.
- Credit the people who supplied writing, designs, or decisions. Keep their contributions distinct from Codex's implementation or drafting work.

## Repository checks and content

- Follow `CONTRIBUTING.md` and applicable local instructions for repository-specific commands, paths, publishing rules, and design decisions. Run checks appropriate to the change. For prose-only edits, use the relevant documentation checks and review the rendered output when it matters.
- Use supplied and approved drafts as the baseline. Preserve the author's voice and verify factual claims against available sources. Ask for material missing details before making claims that depend on them.
- Keep credentials, private records, and unpublished personal details out of public issues, PRs, logs, and artifacts. Review the exact staged diff and final output before publishing an export derived from private inputs.
