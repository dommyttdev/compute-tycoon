# Issue tracker: GitHub

Track issues and PRDs in GitHub Issues for `dommyttdev/compute-tycoon`.
Use `gh` from this repository so it infers the remote automatically.

Always use the local `gh issue` CLI directly for issue creation, reads, updates,
comments, and closure. Do not attempt GitHub connector or MCP issue tools before
`gh issue`.

## Operations

- Create: `gh issue create`
- Read: `gh issue view <number> --comments`
- List: `gh issue list`
- Update labels: `gh issue edit <number> --add-label <label>`
- Close: `gh issue close <number>`

When a skill says to publish work to the issue tracker, create a GitHub issue.
