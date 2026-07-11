# Contributing Guide

## Commit messages

Use Conventional Commits and write the description in Japanese.

```text
<type>[(<scope>)][!]: <Japanese summary>

[Japanese body]

[footer]
```

### Rules

- Use a lowercase English `type` from the table below.
- The optional `scope` should identify the affected module in concise, lowercase
  English.
- Put one ASCII space after the colon.
- Write the summary and body in Japanese.
- Keep the summary concise and omit the trailing Japanese full stop (`。`).
- Keep each commit limited to one logical change.
- For a breaking change, append `!` after the type or scope and add
  `BREAKING CHANGE: <description>` to the footer.
- To reference an issue, add `Refs: #123` or `Closes: #123` to the footer.

### Types

| Type | Purpose |
| --- | --- |
| `feat` | Add a feature |
| `fix` | Fix a bug |
| `docs` | Change documentation only |
| `style` | Change formatting without affecting behavior |
| `refactor` | Improve code without adding a feature or fixing a bug |
| `perf` | Improve performance |
| `test` | Add or update tests |
| `build` | Change the build system or dependencies |
| `ci` | Change CI configuration or scripts |
| `chore` | Perform maintenance not covered by another type |
| `revert` | Revert an earlier commit |

Use `docs`, not `doc`, for documentation changes.

### Valid examples

```text
docs: コミットメッセージ規約を追加
feat(network): ノード間の帯域制限を追加
fix(storage): 容量計算で端数が失われる問題を修正
refactor(executor): ワークロード割り当て処理を分離
test(monitor): 温度警告の境界値テストを追加
feat(config)!: 設定ファイルの形式を変更

BREAKING CHANGE: runtime_config.json の旧形式は読み込めなくなります
```

### Invalid examples

```text
update files
修正
doc: 設計書更新
feat: add network feature
```

These examples are invalid because they are vague, do not follow the required
format, use `doc` instead of `docs`, or describe the change in English.
