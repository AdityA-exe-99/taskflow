# Builds the normal application image, adds test-only tools, and runs tests.
# Removes only the unique temporary Compose project. Reports are retained.
$ErrorActionPreference = 'Stop'
$taskflowRoot = Split-Path -Parent $PSScriptRoot
$taskflowCompose = Join-Path $taskflowRoot 'docker-compose.test.yml'
$taskflowTestProject = 'taskflow-tests-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$taskflowReportDir = Join-Path (Join-Path $taskflowRoot 'test-results') $taskflowTestProject
$taskflowPreviousReports = $env:TASKFLOW_TEST_REPORTS
$taskflowTestExit = 1
$taskflowCleanupExit = 0

foreach ($taskflowRequired in @(
    'Dockerfile', 'Dockerfile.test', 'requirements-test-lock.txt',
    'docker-compose.test.yml', 'tests\run_tests.py',
    'tests\unit\test_validation.py', 'tests\integration\test_application.py'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $taskflowRoot $taskflowRequired) -PathType Leaf)) {
        throw "Required test file is missing: $taskflowRequired"
    }
}

New-Item -ItemType Directory -Path $taskflowReportDir -Force | Out-Null
$env:TASKFLOW_TEST_REPORTS = $taskflowReportDir
Push-Location -LiteralPath $taskflowRoot
try {
    Write-Output "Temporary test project: $taskflowTestProject"
    Write-Output "Reports directory: $taskflowReportDir"
    & docker compose -f $taskflowCompose -p $taskflowTestProject config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'The test Compose configuration is invalid.'
    }

    & docker build --file Dockerfile --tag taskflow-test-runtime:local .
    if ($LASTEXITCODE -ne 0) {
        throw 'The application image could not be built for testing.'
    }

    & docker compose -f $taskflowCompose -p $taskflowTestProject up --build --abort-on-container-exit --exit-code-from tests
    $taskflowTestExit = $LASTEXITCODE
}
finally {
    try {
        & docker compose -f $taskflowCompose -p $taskflowTestProject down --volumes
        $taskflowCleanupExit = $LASTEXITCODE
    }
    finally {
        $env:TASKFLOW_TEST_REPORTS = $taskflowPreviousReports
        Pop-Location
    }
}

Write-Output "Test and coverage exit code: $taskflowTestExit"
Write-Output "Test cleanup exit code: $taskflowCleanupExit"
Write-Output "Reports directory: $taskflowReportDir"
if ($taskflowTestExit -ne 0) {
    exit $taskflowTestExit
}
if ($taskflowCleanupExit -ne 0) {
    exit $taskflowCleanupExit
}
exit 0
