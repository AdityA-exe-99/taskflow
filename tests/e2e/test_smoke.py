"""Smoke checks: the deployed release is up, talks to its database and is the right version."""
import os

from playwright.sync_api import Page, expect


def test_health_reports_app_and_database_ok(page: Page, base_url):
    response = page.request.get(f"{base_url}/health")
    assert response.status == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_deployed_version_is_the_commit_under_test(page: Page, base_url):
    """In the pipeline EXPECTED_VERSION is the commit SHA, proving staging runs the new build."""
    expected = os.environ.get("EXPECTED_VERSION")
    info = page.request.get(f"{base_url}/api/info").json()
    assert info["service"] == "TaskFlow"
    if expected:
        assert info["version"] == expected
        page.goto("/")
        expect(page.locator("footer")).to_contain_text(expected)


def test_dashboard_loads_and_navigation_works(page: Page):
    page.goto("/")
    expect(page.get_by_role("heading", level=1)).to_have_text("TaskFlow dashboard")
    expect(page.get_by_role("region", name="Project and task totals")).to_be_visible()

    nav = page.get_by_role("navigation", name="Main navigation")
    nav.get_by_role("link", name="Projects").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Projects")

    nav.get_by_role("link", name="Dashboard").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("TaskFlow dashboard")
