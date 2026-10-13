TASKFLOW TESTS AND COVERAGE

From the TaskFlow project folder:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-TaskFlow.ps1

The execution-policy option applies only to that PowerShell process.
The script builds a local test base from the normal application Dockerfile,
then adds pinned pytest and coverage tools through Dockerfile.test. The
application's normal Dockerfile and runtime requirements are not modified.
The first build requires network access to download the test packages.

Testing uses a unique taskflow-tests-* Compose project, an internal network,
no published ports and PostgreSQL 17 with temporary storage. Real migrations
are applied before testing. The database URL and initialized engine are
checked before integration tests clear rows. The existing main application
database and its volume are not referenced by this configuration.

Use docker-compose.test.yml alone, not as an override to docker-compose.yml.
The script removes its temporary containers/network/storage after the run,
including on failures. It preserves the test/coverage failure exit code.

The existing test files are retained:
  tests/unit/test_validation.py       - 15 validation tests
  tests/integration/test_application.py - 33 application/database tests

pytest collects these existing unittest TestCase classes. It may additionally
display a count of subtests. No test assertions are removed for coverage.

The equivalent command inside the prepared, isolated test environment is:
  python -m pytest tests/unit tests/integration --cov=app --cov-fail-under=80

The runner also prints missing lines and creates these reports under a new
test-results/taskflow-tests-<id>/ directory for each run:
  coverage.xml     - application line coverage for CI
  junit.xml        - test results for CI
  html/index.html  - browsable coverage report
  .coverage       - coverage measurement data

The gate measures statement/line coverage for all Python files under app.
It does not measure migrations, docker-entrypoint.py, HTML/CSS, browser
interactions, or production deployment. Passing 48 tests alone does not
establish that the coverage threshold passed; check the coverage total and
the final test/coverage exit code. A failed build can leave an empty report
directory; do not treat an earlier run's report as the current run's result.

The existing checks include project/task creation, edits and deletion,
project deletion with tasks while preserving another project, validation,
CSRF, wrong-project and missing-record routes, dashboard counts/order/limits,
database constraints, health, metrics, navigation, escaping and version.
Failure-handling tests deliberately generate application and database errors.
Some failures are simulated; this is not a real network-outage recovery test.

Team follow-up
Upload the actual XML reports from the run as CI artifacts. The configured
test environment and migrations are still required when CI invokes pytest.
This local gate does not by itself verify staging, production, browser tests,
image promotion, monitoring or deployment rollback.

References
https://docs.pytest.org/en/stable/how-to/unittest.html
https://pytest-cov.readthedocs.io/en/latest/config.html
https://pytest-cov.readthedocs.io/en/latest/reporting.html
