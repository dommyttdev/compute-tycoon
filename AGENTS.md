# Agent instructions

Keep agent-only instructions concise and in English to minimize context usage.
Human-facing documentation may use Japanese.

## Commits

Follow the commit rules in `CONTRIBUTING.md`.

- Use Conventional Commits.
- Write the type and optional scope in lowercase English.
- Write the subject and body in Japanese.
- Use `docs`, not `doc`, for documentation changes.
- Do not commit unless the user explicitly asks.

## Agent skills

### Issue tracker

Track work in GitHub Issues. See `docs/agents/issue-tracker.md`.

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
