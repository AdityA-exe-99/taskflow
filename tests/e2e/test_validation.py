"""The server rejects bad input and shows the error to the user, keeping what they typed."""
from playwright.sync_api import Page, expect


def test_blank_project_name_is_rejected(page: Page):
    page.goto("/projects/new")
    # Spaces get past the browser's 'required' check, so this tests the server-side validation
    page.get_by_label("Project name").fill("   ")
    page.get_by_label("Description").fill("kept after the error")
    page.get_by_role("button", name="Create project").click()

    expect(page.get_by_role("alert")).to_contain_text("Enter a project name.")
    expect(page.get_by_label("Description")).to_have_value("kept after the error")


def test_blank_task_title_is_rejected(page: Page, unique_name, cleanup_projects):
    project = f"{unique_name} project"
    cleanup_projects.append(project)
    page.goto("/projects/new")
    page.get_by_label("Project name").fill(project)
    page.get_by_role("button", name="Create project").click()
    page.get_by_role("link", name=project, exact=True).click()

    page.get_by_role("link", name="Add task").click()
    page.get_by_label("Task title").fill("   ")
    page.get_by_role("button", name="Create task").click()
    expect(page.get_by_role("alert")).to_contain_text("Enter a task title.")
    expect(page.get_by_text("Task created successfully.")).to_have_count(0)
