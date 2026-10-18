"""Demo switch for the presentation: running the pipeline with
'simulate_e2e_failure' ticked makes this test fail on staging, so the run
stops before production while the live site keeps the previous version."""
import os

import pytest


def test_demo_failure_switch_is_off():
    if os.environ.get("E2E_SIMULATE_FAILURE") == "true":
        pytest.fail("Deliberate failure (simulate_e2e_failure was ticked): production must be skipped")
