# Git Branch Rules

## Purpose

Use short-lived task branches to isolate one issue or logical change while
protecting user work and keeping shared-worktree coordination predictable.

## Ownership

The root agent exclusively owns branch operations, the Git index, commits, and
history. Subagents edit only their assigned files and report changes to root.
Root may create or switch branches as normal task preparation without extra user
authorization. One approval covers the reviewed change through branch cleanup.

## Approval

Require exactly one approver per change. QA is the default approver. Use the
manager instead when the change affects requirements, architecture, security,
persistence compatibility, release risk, or when QA cannot decide. Do not request
both unless the user explicitly requires dual approval.

The approver reviews the complete diff and relevant verification, then reports
`OK` with the branch name and reviewed worktree fingerprint or commit SHA. That
approval authorizes root to commit, push, create or update the PR, submit the PR
review, merge after required checks pass, and delete the branch. Explicit user
authorization may replace agent approval.

Any content change after approval invalidates it. Reverification that does not
change tracked content does not. Root must obtain one new approval for the updated
diff; the same approver may issue it. An approval never applies to another branch,
PR, or change.

## Naming

Branch from `main` using:

```text
<type>/<issue-number>-<slug>
<type>/<slug>                 # minor logical change that needs no issue
```

Use a Conventional Commit type, lowercase ASCII, and a concise kebab-case slug.
Examples: `feat/123-network-bandwidth`, `fix/storage-rounding`, and
`docs/cli-reference`. Do not include people, agent names, or dates.

## Lifecycle

1. Before any workspace write, root inspects the current branch and worktree.
2. On a clean `main`, root creates one branch for the issue or logical change.
   When already on the appropriate task branch, continue without creating or
   switching branches.
3. Subagents perform bounded work; root integrates and verifies the diff.
4. QA approves normal changes; the manager approves high-risk or exceptional
   changes. Only one of them reviews the change.
5. After approval, root performs the authorized Git and PR operations without
   requesting approval again at each stage.
6. Root merges only after required checks pass, then deletes the branch when safe.

With a dirty worktree, do not create or switch branches. Continue only when the
current branch is appropriate for the same task; otherwise stop. Never stash,
discard, overwrite, or mix changes to make preparation possible.

## Issue, Commit, and PR Linkage

- Keep each branch, commit, and PR limited to one logical change.
- Follow `CONTRIBUTING.md` for commit messages.
- Use `Refs: #123` when referencing an issue. Use `Closes: #123` only when the
  change fully resolves it; prefer closing from the PR body.
- Target `main`. Use a Conventional Commit-style PR title and do not combine
  unrelated issues.

## Shared-Worktree Concurrency

- Read-only agents may run concurrently.
- Writers may run concurrently only when their assigned file sets do not overlap.
- Sequence work that touches the same files or has dependencies.
- Subagents share the current branch; they must not create per-agent branches.
- Use separate worktrees for truly parallel branches only when explicitly
  requested.

## Prohibited Operations

- Direct changes or commits on `main`.
- Creating or switching branches with any uncommitted change.
- Subagent branch, index, commit, stash, merge, rebase, push, or history changes.
- Unauthorized stash, reset, discard, overwrite, force-push, or history rewrite.
- Accumulating unrelated tasks on one branch.
- Acting on missing, ambiguous, stale, or out-of-scope approval.
- Requesting both QA and manager approval by default.
- Treating branch creation or switching as approval to commit, push, open a PR,
  review, merge, or delete a branch.
