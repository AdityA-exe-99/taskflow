"""Apply migrations, then run pytest with an 80% application coverage gate."""

import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit


def main():
    target = urlsplit(os.environ.get("DATABASE_URL", ""))
    if not (
        os.environ.get("TASKFLOW_TESTING") == "1"
        and target.scheme == "postgresql"
        and target.hostname == "test-db"
        and target.port == 5432
        and target.username == "taskflow_test"
        and target.path == "/taskflow_test"
    ):
        raise RuntimeError("Refusing to run outside the dedicated test database.")

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    for group in ("unit", "integration"):
        directory = root / "tests" / group
        if not directory.is_dir() or not any(directory.glob("test_*.py")):
            raise RuntimeError(f"Missing tests in tests/{group}.")

    reports = root / "test-results"
    reports.mkdir(parents=True, exist_ok=True)
    os.environ["COVERAGE_FILE"] = str(reports / ".coverage")
    print("Applying migrations to the temporary test database...", flush=True)
    result = subprocess.run([
        sys.executable, "-m", "flask", "--app", "app", "db", "upgrade",
    ])
    if result.returncode:
        return result.returncode

    print("Running unit and integration tests; minimum coverage is 80%...", flush=True)
    return subprocess.run([
        sys.executable, "-m", "pytest", "tests/unit", "tests/integration",
        "-v", "--tb=short", "-p", "no:cacheprovider",
        "--cov=app", "--cov-fail-under=80", "--cov-precision=2",
        "--cov-report=term-missing",
        f"--cov-report=xml:{reports / 'coverage.xml'}",
        f"--cov-report=html:{reports / 'html'}",
        f"--junitxml={reports / 'junit.xml'}",
    ]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
