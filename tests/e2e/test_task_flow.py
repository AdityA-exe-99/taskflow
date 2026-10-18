"""The main user journey, through the real UI and database:
create project -> add task -> edit it -> delete task -> delete project."""
from playwright.sync_api import Page, expect


def test_full_project_and_task_lifecycle(page: Page, unique_name, cleanup_projects):
    project = f"{unique_name} project"
    task = f"{unique_name} task"
    cleanup_projects.append(project)
    notice = page.get_by_role("status")

    # Create a project
    page.goto("/projects")
    page.get_by_role("link", name="Create project").click()
    page.get_by_label("Project name").fill(project)
    page.get_by_label("Description").fill("Created by the staging E2E test")
    page.get_by_role("button", name="Create project").click()
    expect(notice).to_contain_text("Project created successfully.")
    page.get_by_role("link", name=project, exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_have_text(project)
    expect(page.get_by_text("No tasks yet")).to_be_visible()

    # Add a task
    page.get_by_role("link", name="Add task").click()
    page.get_by_label("Task title").fill(task)
    page.get_by_label("Priority").select_option("high")
    page.get_by_label("Due date").fill("2030-01-15")
    page.get_by_role("button", name="Create task").click()
    expect(notice).to_contain_text("Task created successfully.")
    card = page.locator("article.card").filter(has=page.get_by_role("heading", name=task, exact=True))
    expect(card).to_contain_text("To do")
    expect(card).to_contain_text("High")
    expect(card).to_contain_text("15 Jan 2030")

    # Edit it: move to In progress
    page.get_by_role("link", name=f"Edit {task}", exact=True).click()
    expect(page.get_by_role("heading", level=1)).to_have_text("Edit task")
    page.get_by_label("Status").select_option("in_progress")
    page.get_by_role("button", name="Save changes").click()
    expect(notice).to_contain_text("Task updated successfully.")
    expect(card).to_contain_text("In progress")

    # Delete the task
    page.get_by_role("link", name=f"Delete {task}", exact=True).click()
    page.get_by_role("button", name="Confirm deletion").click()
    expect(notice).to_contain_text("Task deleted successfully.")
    expect(page.get_by_role("heading", name=task, exact=True)).to_have_count(0)

    # Delete the project
    page.goto("/projects")
    page.get_by_role("link", name=f"Delete project {project}", exact=True).click()
    page.get_by_role("button", name="Delete project").click()
    expect(notice).to_contain_text("Project deleted successfully.")
    expect(page.get_by_role("link", name=project, exact=True)).to_have_count(0)


def test_open_task_appears_on_dashboard(page: Page, unique_name, cleanup_projects):
    project = f"{unique_name} project"
    task = f"{unique_name} urgent"
    cleanup_projects.append(project)

    page.goto("/projects/new")
    page.get_by_label("Project name").fill(project)
    page.get_by_role("button", name="Create project").click()
    page.get_by_role("link", name=project, exact=True).click()
    page.get_by_role("link", name="Add task").click()
    page.get_by_label("Task title").fill(task)
    # Earliest possible due date, so it is always in the dashboard's top six
    page.get_by_label("Due date").fill("2000-01-01")
    page.get_by_role("button", name="Create task").click()

    page.goto("/")
    open_card = page.locator("article.card").filter(has=page.get_by_role("heading", name=task, exact=True))
    expect(open_card).to_be_visible()
    expect(open_card).to_contain_text("Overdue")
