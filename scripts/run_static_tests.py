from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

CHECKS: tuple[tuple[str, Sequence[str]], ...] = (
    (
        "compile",
        (
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "main.py",
            "hardware.py",
            "hardware_sim",
            "tests",
        ),
    ),
    ("ruff check", (sys.executable, "-m", "ruff", "check", ".")),
    ("ruff format", (sys.executable, "-m", "ruff", "format", "--check", ".")),
    (
        "mypy",
        (
            sys.executable,
            "-m",
            "mypy",
            "main.py",
            "hardware.py",
            "hardware_sim",
        ),
    ),
    (
        "pytest with coverage",
        (sys.executable, "-m", "coverage", "run", "-m", "pytest"),
    ),
    ("coverage report", (sys.executable, "-m", "coverage", "report")),
)


def main() -> int:
    for name, command in CHECKS:
        print(f"==> {name}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
