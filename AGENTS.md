# Agent instructions

Keep agent-only instructions concise and in English to minimize context usage.
Human-facing documentation may use Japanese.

## Encoding

- When reading Japanese text in PowerShell, set console output to UTF-8 and use
  `Get-Content -Encoding UTF8`; do not rely on the session default encoding.

## Commits

Follow the commit rules in `CONTRIBUTING.md`.

- Use Conventional Commits.
- Write the type and optional scope in lowercase English.
- Write the subject and body in Japanese.
- Use `docs`, not `doc`, for documentation changes.
- Do not commit unless the user explicitly asks.
- A user instruction to perform work authorizes the complete delivery workflow:
  implement, verify, commit, push, open a PR, obtain the required review, merge,
  and delete the task branch. Do not pause for separate approval at each step.
- Stop before completion only for a real blocker such as ambiguous scope,
  unrelated worktree changes, merge conflicts, failing required checks, missing
  credentials or permissions, or review changes that require user direction.

## Branches

Follow `docs/agents/git-branches.md`.

- The root agent exclusively owns branches, the Git index, commits, and history.
- Before writing, root inspects the branch and worktree. On clean `main`, create a
  short-lived branch: `<type>/<issue>-<slug>` or `<type>/<slug>`. Continue without
  switching when already on the appropriate task branch.
- Subagents must not switch, create, merge, rebase, or delete branches; stage,
  commit, stash, or push changes; or otherwise alter the Git index or history.
- With a dirty worktree, do not create or switch branches. Stop if the current
  branch is not appropriate for the task.
- Root needs no extra permission to prepare a branch. After the user instructs
  the work, root may commit, push, and open the PR. After one designated approver
  accepts the complete PR diff, root may record the review, merge, and delete the
  branch. See the approval rules.

## Agent skills

### Issue tracker

Track work in GitHub Issues. See `docs/agents/issue-tracker.md`.
Always use the local `gh issue` CLI for GitHub Issue operations. Do not try a
GitHub connector or MCP issue tool first.

### Triage labels

Use the canonical workflow labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use the single-context domain layout. See `docs/agents/domain.md`.

## Coding

Apply rules in this order: correctness and invariants, least surprise, locality,
readability, reuse, then extensibility.

- Read `CONTEXT.md` and relevant ADRs before changing domain behavior.
- Use canonical domain terms and preserve documented module boundaries.
- Prefer the simplest current solution; do not add speculative abstractions,
  extension points, compatibility layers, or configuration.
- Keep behavior with the object that owns the state and invariant. Keep CLI,
  persistence, and data-format concerns at their boundaries.
- Prefer immutable value objects, composition, and narrow typed `Protocol`s over
  shared mutable state, inheritance, and broad interfaces.
- Make dependencies, side effects, mutation, defaults, return values, and failure
  modes explicit. Do not silently recover from invalid state.
- Keep validation, mutation, I/O, and presentation separate. Each unit should have
  one clear reason to change.
- Treat DRY as one source of truth for knowledge, not removal of similar syntax.
  Extract only behavior with the same meaning, invariant, and reason to change.
- Keep public APIs minimal. Preserve compatibility unless a breaking change is
  requested; update `hardware_sim/__init__.py` and `hardware.py` exports together.
- Change persistent models, save, and load together. Mutate save-relevant game
  state under the game lock and increment the state version.
- Keep `NetworkTopology` immutable. Release allocated resources in `finally` paths.
- Add or update focused tests for changed behavior and regressions. Run the checks
  in `docs/development/quality.md`.
- Update affected design docs. Add an ADR for new cross-module constraints,
  dependency directions, public contracts, or persistence strategies.

## Orchestration

The root agent is the control tower: clarify scope, decompose work, assign bounded
tasks, track dependencies, integrate results, and own the final answer.

- Delegate non-trivial exploration, implementation, testing, and review to the
  narrowest matching project subagent. Keep trivial tasks in the root thread.
- Give each subagent only the files, constraints, acceptance criteria, and output
  format it needs. Request concise findings, not raw logs or full file contents.
- Parallelize independent read-only tasks. Use one writer per overlapping file set;
  sequence dependent or conflicting edits.
- Use `architect` for impact analysis and design, `engineer` for bounded changes,
  and `qa` for independent verification.
- Do not ask subagents to re-plan the whole task or repeat context already supplied.
- The root agent reviews diffs, resolves conflicts, runs final proportional checks,
  and reports only integrated outcomes.
