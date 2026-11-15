# Contributing

Follow [AGENTS.md](AGENTS.md). The current default branch is `master`; all changes
reach it through pull requests. Do not rename it or change repository settings
without the owner's explicit authorization.

## Before making changes

Find an existing issue covering the work, or create one. Confirm scope,
dependencies, missing inputs, and readiness. Use the standard native issue type
`Bug`, `Feature`, or `Task` and set the existing native fields:

| Field | Values / guidance |
| --- | --- |
| Priority | Urgent, High, Medium, Low; preserve owner-set values |
| Effort | Low, Medium, High; estimate scope and uncertainty independently |
| Start date | Actual first work date; blank before starting |
| Target date | Only when a target has been established |

Use priority to select the highest-priority actionable issue, or unblock its
prerequisite. Audit all open issues for missing or ambiguous priorities during
triage. Record the reason for priority changes, and preserve completed issues'
historical priorities. If tooling cannot set Priority, temporarily use a
`## Priority` section in the issue body. A readable native value is authoritative.
Issue forms collect fallback information; verify and set the native type and
fields during triage, rather than treating a form answer as a native field.

Fetch the default branch and create an issue branch:

```sh
git fetch origin
git switch -c <issue-number>-<short-description> origin/master
```

If the checkout contains other work, preserve it and use a separate worktree.
Use local file edits and `git` to commit and push; use `gh` for issues, labels,
pull requests, review feedback, and CI status.

## Pull requests

Use the PR template. Describe the concrete problem, resulting behavior, and
relevant validation. Reference at least one existing issue in this repository:
`Closes #N` for completed work targeting the default branch, or `Related to #N`
for partial work, with remaining work stated. Cross-repository issues may provide
context but do not replace the local tracking issue.

Apply exactly one change-type label from this catalog. Other labels are allowed,
but do not add a second change-type label. Recheck the label if scope changes.
The machine-readable catalog is [scripts/change_type_labels.json](scripts/change_type_labels.json).

| Change-type label | Use |
| --- | --- |
| bug | Fix incorrect behavior |
| enhancement | Add or improve asset or product functionality |
| documentation | Prose, usage documentation, or editorial changes |
| maintenance | Workflow, CI, tooling, configuration, dependency, or repository upkeep |

Retain other existing labels; Priority and Effort use native fields, not labels.
The setup task adds `maintenance`; the other catalog labels already exist.

When Codex creates or substantially implements a PR, add an **AI assistance:**
footer describing its actual contribution and the verified authenticated account.
Include model/version only if verified. Credit the owner's designs, writing,
and decisions separately. Never invent unavailable attribution details.

Before reporting a PR as ready, inspect review feedback and CI:

```sh
gh pr view <number> --comments
gh pr checks <number>
```

Report checks that cannot run and why. Do not merge without owner direction.

## Checks

Use Python 3.10 or newer, with no external dependencies:

```sh
python3 -m unittest discover -s tests -v
git diff --check
```

CI runs tests on Python 3.10 and 3.14. Asset-specific checks belong with the asset
implementation; do not require an unmerged generator in this setup change.

The `PR policy / Issue and change-type label` workflow validates PR metadata
using only default-branch code, without checking out or running PR code. It checks
that at least one referenced local issue exists and is an issue rather than a PR,
and that exactly one catalog label is applied. It reruns when descriptions or
labels change. Because this workflow uses `pull_request_target`, it starts only
after the workflow is merged into the default branch; validate the first setup
PR manually with the same script.

The existing ruleset requires PRs, squash merging, and blocks deletion and force
pushes, with no bypass actors. It currently requires zero reviewer approvals and
no status checks. After CI has run, the owner can require `Tests (3.10)`,
`Tests (3.14)`, and `Issue and change-type label` in that ruleset. Preserve all
other protections. This PR does not change those repository settings.
