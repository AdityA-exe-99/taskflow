"""Shared setup for the browser (end-to-end) tests.

Owner: Abhinav (Test/Staging). These tests drive a real Chromium browser
against a running TaskFlow (staging in the pipeline, or a local copy).
Run with:  pytest tests/e2e --base-url http://127.0.0.1:8000
"""
import os
import uuid

import pytest
from playwright.sync_api import Page, expect

expect.set_options(timeout=10_000)


@pytest.fixture(autouse=True)
def _require_base_url(base_url):
    if not base_url:
        pytest.fail("Pass --base-url, e.g. --base-url http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # Only for running outside the Playwright image with a different browser build
    path = os.environ.get("E2E_CHROMIUM_PATH")
    if path:
        return {**browser_type_launch_args, "executable_path": path}
    return browser_type_launch_args


@pytest.fixture
def unique_name():
    """Unique prefix so tests never clash with real data or with each other."""
    return f"E2E {uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_projects(page: Page):
    """Tests register project names here; any left behind are deleted afterwards,
    so a failed run does not leave test data on staging."""
    names = []
    yield names
    for name in names:
        page.goto("/projects")
        delete_link = page.get_by_role("link", name=f"Delete project {name}", exact=True)
        if delete_link.count():
            delete_link.click()
            page.locator("form button[type=submit]").click()
