# Static testing

Install the development tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run all static checks:

```powershell
.\.venv\Scripts\python.exe scripts\run_static_tests.py
```

The static test entry point currently runs:

- `compileall` for syntax and import-time bytecode compilation checks.
- `ruff check` for lint errors and import ordering.
- `ruff format --check` for formatting drift.
- `mypy` for gradual type checking.

`mypy` is intentionally configured as a gradual baseline. Existing dynamic JSON
parsing and untyped runtime objects are not treated as failures yet, so the
static test suite can run cleanly while stricter typing is added incrementally.
