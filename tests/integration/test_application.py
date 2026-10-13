"""HTTP routes and real PostgreSQL behaviour, using only the test stack."""

import os
import re
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

target = urlsplit(os.environ.get("DATABASE_URL", ""))
if not (
    os.environ.get("TASKFLOW_TESTING") == "1"
    and target.scheme == "postgresql"
    and target.hostname == "test-db"
    and target.port == 5432
    and target.username == "taskflow_test"
    and target.path == "/taskflow_test"
):
    raise RuntimeError("Integration tests require the dedicated test database.")

import psycopg
from sqlalchemy import delete, func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import app
from app.extensions import db
from app.models import Project, Task


class ApplicationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        # Also inspect the initialized engine: another test may have imported
        # the global application before this module.
        with app.app_context():
            url = db.engine.url
            if not (
                url.get_backend_name() == "postgresql"
                and url.host == "test-db"
                and url.port == 5432
                and url.username == "taskflow_test"
                and url.database == "taskflow_test"
            ):
                raise RuntimeError("Refusing to clear a non-test database.")

    def setUp(self):
        self.client = app.test_client()
        self.clear_test_rows()
        self.addCleanup(self.clear_test_rows)

    def clear_test_rows(self):
        with app.app_context():
            db.session.rollback()
            db.session.execute(delete(Task))
            db.session.execute(delete(Project))
            db.session.commit()

    def seed_project(self, name="Test project", description=""):
        with app.app_context():
            project = Project(name=name, description=description)
            db.session.add(project)
            db.session.commit()
            return project.id

    def seed_task(self, project_id, title="Test task", **changes):
        values = {
            "project_id": project_id, "title": title, "description": "",
            "status": "todo", "priority": "medium", "due_date": None,
        }
        values.update(changes)
        with app.app_context():
            task = Task(**values)
            db.session.add(task)
            db.session.commit()
            return task.id

    def counts(self):
        with app.app_context():
            return (
                db.session.scalar(db.select(func.count(Project.id))),
                db.session.scalar(db.select(func.count(Task.id))),
            )

    def task_values(self, task_id):
        with app.app_context():
            task = db.session.get(Task, task_id)
            if task is None:
                return None
            return {
                field: getattr(task, field)
                for field in (
                    "project_id", "title", "description", "status",
                    "priority", "due_date",
                )
            }

    def token(self, path, client=None):
        client = client or self.client
        response = client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'name="csrf_token"\s+value="([^"]+)"',
            response.get_data(as_text=True),
        )
        self.assertIsNotNone(match, "The form must contain a CSRF token.")
        return match.group(1)

    def submit(self, path, **values):
        values["csrf_token"] = self.token(path)
        return self.client.post(path, data=values)

    def task_form(self, **changes):
        values = {
            "title": "Release check", "description": "Check the release",
            "status": "todo", "priority": "medium", "due_date": "",
        }
        values.update(changes)
        return values

    def assert_redirect(self, response, path):
        self.assertEqual(response.status_code, 303)
        self.assertEqual(urlsplit(response.headers["Location"]).path, path)

    def dashboard(self):
        # Keep overdue and due-today checks independent of the run date.
        with patch("app.views.datetime") as clock:
            clock.now.return_value = datetime(
                2026, 10, 12, 12, tzinfo=timezone.utc,
            )
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        cards = {
            label.strip(): int(value)
            for label, value in re.findall(
                r"<dt>\s*([^<]+)</dt>\s*<dd>\s*(\d+)\s*</dd>", html,
            )
        }
        self.assertEqual(len(cards), 6)
        return cards, html

    def test_migration_created_tables_and_recorded_revision(self):
        with app.app_context():
            revision = db.session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            self.assertTrue(revision)
        self.assertEqual(self.counts(), (0, 0))

    def test_empty_dashboard_and_projects(self):
        cards, html = self.dashboard()
        self.assertEqual(sum(cards.values()), 0)
        self.assertIn("No open tasks", html)
        response = self.client.get("/projects")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No projects yet", response.data)

    def test_navigation_and_all_existing_record_pages_render(self):
        project = self.seed_project()
        task = self.seed_task(project)
        for path in (
            "/", "/projects", "/projects/new", f"/projects/{project}",
            f"/projects/{project}/delete", f"/projects/{project}/tasks/new",
            f"/projects/{project}/tasks/{task}/edit",
            f"/projects/{project}/tasks/{task}/delete",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertRegex(html, r'href="/">\s*Dashboard\s*</a>')
                self.assertRegex(html, r'href="/projects">\s*Projects\s*</a>')

    def test_project_creation_persists_trimmed_fields_and_redirects(self):
        response = self.submit(
            "/projects/new", name="  Release  ", description="  Ready  ",
        )
        self.assert_redirect(response, "/projects")
        with app.app_context():
            project = db.session.scalars(db.select(Project)).one()
            self.assertEqual((project.name, project.description), ("Release", "Ready"))
        response = self.client.get("/projects")
        self.assertIn(b"Project created successfully.", response.data)
        self.assertEqual(self.counts(), (1, 0))

    def test_invalid_project_creation_preserves_input_without_inserting(self):
        response = self.submit(
            "/projects/new", name="   ", description="Keep this description",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter a project name.", response.data)
        self.assertIn(b"Keep this description", response.data)
        self.assertEqual(self.counts(), (0, 0))

    def test_task_creation_persists_every_field(self):
        project = self.seed_project()
        response = self.submit(
            f"/projects/{project}/tasks/new",
            **self.task_form(status="in_progress", priority="high", due_date="2026-10-19"),
        )
        self.assert_redirect(response, f"/projects/{project}")
        with app.app_context():
            task_id = db.session.scalars(db.select(Task.id)).one()
        self.assertEqual(self.task_values(task_id), {
            "project_id": project, "title": "Release check",
            "description": "Check the release", "status": "in_progress",
            "priority": "high", "due_date": date(2026, 10, 19),
        })
        response = self.client.get(f"/projects/{project}")
        self.assertIn(b"Task created successfully.", response.data)
        self.assertIn(b"Release check", response.data)

    def test_invalid_task_creation_does_not_insert(self):
        project = self.seed_project()
        for changes in (
            {"title": " "}, {"status": "finished"},
            {"priority": "urgent"}, {"due_date": "2026-02-29"},
        ):
            with self.subTest(changes=changes):
                response = self.submit(
                    f"/projects/{project}/tasks/new",
                    **self.task_form(**changes),
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(b"Check the release", response.data)
                self.assertEqual(self.counts(), (1, 0))

    def test_task_edit_persists_fields_and_can_clear_due_date(self):
        project = self.seed_project()
        task = self.seed_task(project, due_date=date(2026, 10, 19))
        path = f"/projects/{project}/tasks/{task}/edit"
        response = self.submit(path, **self.task_form(
            title="Updated", description="New description", status="done",
            priority="low", due_date="2026-10-20",
        ))
        self.assert_redirect(response, f"/projects/{project}")
        self.assertEqual(self.task_values(task), {
            "project_id": project, "title": "Updated",
            "description": "New description", "status": "done",
            "priority": "low", "due_date": date(2026, 10, 20),
        })
        response = self.client.get(f"/projects/{project}")
        self.assertIn(b"Task updated successfully.", response.data)
        self.assertIn(b"Updated", response.data)
        response = self.submit(path, **self.task_form(due_date=""))
        self.assert_redirect(response, f"/projects/{project}")
        self.assertIsNone(self.task_values(task)["due_date"])

    def test_task_status_transitions_are_saved(self):
        project = self.seed_project()
        task = self.seed_task(project)
        for status in ("in_progress", "done", "todo"):
            with self.subTest(status=status):
                response = self.submit(
                    f"/projects/{project}/tasks/{task}/edit",
                    **self.task_form(status=status),
                )
                self.assert_redirect(response, f"/projects/{project}")
                self.assertEqual(self.task_values(task)["status"], status)

    def test_invalid_task_edit_leaves_original_record_unchanged(self):
        project = self.seed_project()
        task = self.seed_task(project, due_date=date(2026, 10, 20))
        original = self.task_values(task)
        for changes in (
            {"title": ""}, {"status": "finished"},
            {"priority": "urgent"}, {"due_date": "2026-02-29"},
        ):
            with self.subTest(changes=changes):
                response = self.submit(
                    f"/projects/{project}/tasks/{task}/edit",
                    **self.task_form(**changes),
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.task_values(task), original)

    def test_task_delete_confirmation_and_cancel_do_not_delete(self):
        project = self.seed_project()
        task = self.seed_task(project)
        response = self.client.get(f"/projects/{project}/tasks/{task}/delete")
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.get_data(as_text=True),
            rf'href="/projects/{project}">\s*Cancel\s*</a>',
        )
        self.assertEqual(self.client.get(f"/projects/{project}").status_code, 200)
        self.assertIsNotNone(self.task_values(task))

    def test_task_delete_removes_only_selected_task(self):
        project = self.seed_project()
        removed = self.seed_task(project, title="Remove this task")
        retained = self.seed_task(project, title="Retain this task")
        response = self.submit(f"/projects/{project}/tasks/{removed}/delete")
        self.assert_redirect(response, f"/projects/{project}")
        self.assertIsNone(self.task_values(removed))
        self.assertIsNotNone(self.task_values(retained))
        self.assertEqual(self.counts(), (1, 1))
        response = self.client.get(f"/projects/{project}")
        self.assertIn(b"Task deleted successfully.", response.data)
        self.assertNotIn(b"Remove this task", response.data)

    def test_project_delete_confirmation_and_cancel_keep_tasks(self):
        project = self.seed_project()
        task = self.seed_task(project)
        response = self.client.get(f"/projects/{project}/delete")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Delete project and its tasks", html)
        self.assertRegex(html, r"Tasks currently in this project:\s*<strong>1</strong>")
        self.assertRegex(html, r'href="/projects">\s*Cancel\s*</a>')
        self.assertEqual(self.client.get("/projects").status_code, 200)
        self.assertIsNotNone(self.task_values(task))
        self.assertEqual(self.counts(), (1, 1))

    def test_deleting_project_cascades_without_affecting_other_project(self):
        removed_project = self.seed_project("Remove project")
        removed_tasks = [
            self.seed_task(removed_project, title=f"Remove task {index}")
            for index in range(3)
        ]
        retained_project = self.seed_project("Retain project")
        retained_task = self.seed_task(retained_project, title="Keep this")
        response = self.submit(f"/projects/{removed_project}/delete")
        self.assert_redirect(response, "/projects")
        # Read the one-time success message on the redirect destination
        # before another rendered page consumes it from the session.
        response = self.client.get(response.headers["Location"])
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project deleted successfully.", response.data)
        self.assertNotIn(b"Remove project", response.data)
        self.assertIn(b"Retain project", response.data)
        self.assertEqual(self.counts(), (1, 1))
        for task_id in removed_tasks:
            self.assertIsNone(self.task_values(task_id))
        self.assertEqual(self.task_values(retained_task)["project_id"], retained_project)
        self.assertEqual(self.client.get(f"/projects/{removed_project}").status_code, 404)
        self.assertEqual(self.client.get(f"/projects/{retained_project}").status_code, 200)

    def test_deleting_empty_project_succeeds(self):
        project = self.seed_project()
        response = self.submit(f"/projects/{project}/delete")
        self.assert_redirect(response, "/projects")
        self.assertEqual(self.counts(), (0, 0))

    def test_every_write_route_rejects_missing_and_incorrect_csrf(self):
        project = self.seed_project()
        task = self.seed_task(project)
        original = self.task_values(task)
        for path in (
            "/projects/new", f"/projects/{project}/tasks/new",
            f"/projects/{project}/tasks/{task}/edit",
            f"/projects/{project}/tasks/{task}/delete",
            f"/projects/{project}/delete",
        ):
            self.token(path)
            for supplied_token in (None, "incorrect-token"):
                with self.subTest(path=path, token=supplied_token):
                    values = self.task_form()
                    values["name"] = "Must not be created"
                    if supplied_token is not None:
                        values["csrf_token"] = supplied_token
                    response = self.client.post(path, data=values)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(self.counts(), (1, 1))
                    self.assertEqual(self.task_values(task), original)

    def test_csrf_token_from_another_session_is_rejected(self):
        other_client = app.test_client()
        other_token = self.token("/projects/new", client=other_client)
        self.token("/projects/new")
        response = self.client.post(
            "/projects/new", data={"name": "Rejected", "csrf_token": other_token},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.counts(), (0, 0))

    def test_task_cannot_be_edited_or_deleted_through_another_project(self):
        owner = self.seed_project("Owner")
        other = self.seed_project("Other")
        task = self.seed_task(owner)
        original = self.task_values(task)
        token = self.token("/projects/new")
        for action in ("edit", "delete"):
            path = f"/projects/{other}/tasks/{task}/{action}"
            with self.subTest(action=action):
                self.assertEqual(self.client.get(path).status_code, 404)
                response = self.client.post(
                    path, data={**self.task_form(), "csrf_token": token},
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(self.task_values(task), original)

    def test_missing_project_and_task_routes_return_404(self):
        project = self.seed_project()
        token = self.token("/projects/new")
        for path in (
            "/projects/2147483647", "/projects/2147483647/delete",
            "/projects/2147483647/tasks/new",
            f"/projects/{project}/tasks/2147483647/edit",
            f"/projects/{project}/tasks/2147483647/delete",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
                if path != "/projects/2147483647":
                    response = self.client.post(
                        path, data={**self.task_form(), "csrf_token": token},
                    )
                    self.assertEqual(response.status_code, 404)
        self.assertEqual(self.counts(), (1, 0))

    def test_dashboard_counts_exclude_done_today_and_undated_from_overdue(self):
        project = self.seed_project()
        self.seed_project("Second")
        self.seed_task(project, title="Past todo", due_date=date(2026, 10, 11))
        self.seed_task(project, title="Past progress", status="in_progress",
                       due_date=date(2026, 10, 10))
        self.seed_task(project, title="Past done", status="done",
                       due_date=date(2026, 10, 9))
        self.seed_task(project, title="Due today", due_date=date(2026, 10, 12))
        self.seed_task(project, title="Future", due_date=date(2026, 10, 13))
        self.seed_task(project, title="Undated")
        cards, html = self.dashboard()
        self.assertEqual(cards, {
            "Projects": 2, "Total tasks": 6, "To do": 4,
            "In progress": 1, "Done": 1, "Overdue": 2,
        })
        self.assertNotIn("Past done", html)
        self.assertEqual(html.count('class="overdue-label"'), 2)

    def test_dashboard_updates_after_overdue_task_is_completed(self):
        project = self.seed_project()
        task = self.seed_task(project, due_date=date(2026, 10, 11))
        self.assertEqual(self.dashboard()[0]["Overdue"], 1)
        response = self.submit(
            f"/projects/{project}/tasks/{task}/edit",
            **self.task_form(status="done", due_date="2026-10-11"),
        )
        self.assert_redirect(response, f"/projects/{project}")
        cards, html = self.dashboard()
        self.assertEqual((cards["Done"], cards["To do"], cards["Overdue"]), (1, 0, 0))
        self.assertIn("No open tasks", html)
        self.assertEqual(self.task_values(task)["due_date"], date(2026, 10, 11))

    def test_dashboard_orders_by_due_date_then_id_with_undated_last(self):
        project = self.seed_project()
        self.seed_task(project, title="Undated item")
        self.seed_task(project, title="Later item", due_date=date(2026, 10, 20))
        self.seed_task(project, title="First tie", due_date=date(2026, 10, 11))
        self.seed_task(project, title="Second tie", due_date=date(2026, 10, 11))
        _, html = self.dashboard()
        headings = re.findall(r"<h3>\s*([^<]+)</h3>", html)
        self.assertEqual(headings, ["First tie", "Second tie", "Later item", "Undated item"])

    def test_dashboard_shows_at_most_six_open_tasks(self):
        project = self.seed_project()
        for day in range(18, 10, -1):
            self.seed_task(project, title=f"Due {day}", due_date=date(2026, 10, day))
        self.seed_task(project, title="Undated last")
        self.seed_task(project, title="Completed hidden", status="done")
        cards, html = self.dashboard()
        self.assertEqual(cards["Total tasks"], 10)
        self.assertEqual(
            re.findall(r"<h3>\s*([^<]+)</h3>", html),
            [f"Due {day}" for day in range(11, 17)],
        )

    def test_user_text_is_escaped_in_rendered_pages(self):
        project = self.seed_project("<script>alert(1)</script>")
        task = self.seed_task(project, title="<script>alert(2)</script>")
        for path in (
            "/", "/projects", f"/projects/{project}",
            f"/projects/{project}/delete", f"/projects/{project}/tasks/{task}/edit",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(b"<script>alert(", response.data)
                self.assertIn(b"&lt;script&gt;", response.data)

    def test_database_rejects_invalid_task_values(self):
        project = self.seed_project()
        for changes in (
            {"title": "   "}, {"status": "finished"}, {"priority": "urgent"},
        ):
            with self.subTest(changes=changes), app.app_context():
                values = {"project_id": project, "title": "Valid"}
                values.update(changes)
                db.session.add(Task(**values))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()
        self.assertEqual(self.counts(), (1, 0))

    def test_database_rejects_blank_project_and_orphan_task(self):
        with app.app_context():
            db.session.add(Project(name="  "))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()
            db.session.add(Task(project_id=2147483647, title="Orphan"))
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()
        self.assertEqual(self.counts(), (0, 0))

    def test_commit_failure_returns_503_and_rolls_back_each_write_route(self):
        project = self.seed_project()
        task = self.seed_task(project)
        original = self.task_values(task)
        cases = (
            ("/projects/new", {"name": "Uncommitted"}),
            (f"/projects/{project}/tasks/new", self.task_form()),
            (f"/projects/{project}/tasks/{task}/edit", self.task_form()),
            (f"/projects/{project}/tasks/{task}/delete", {}),
            (f"/projects/{project}/delete", {}),
        )
        for path, values in cases:
            with self.subTest(path=path):
                token = self.token(path)
                with patch.object(
                    db.session, "commit",
                    side_effect=SQLAlchemyError("simulated commit failure"),
                ):
                    response = self.client.post(
                        path, data={**values, "csrf_token": token},
                    )
                self.assertEqual(response.status_code, 503)
                self.assertIn(b"Please try again.", response.data)
                self.assertEqual(self.counts(), (1, 1))
                self.assertEqual(self.task_values(task), original)

    def test_health_checks_the_real_test_database(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"db": "ok", "status": "ok"})

    def test_health_returns_503_for_simulated_connection_failure(self):
        with patch("app.psycopg.connect", side_effect=psycopg.OperationalError("simulated")):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"db": "unavailable", "status": "error"})
        self.assertNotIn(b"simulated", response.data)

    def test_health_returns_503_when_database_url_is_missing(self):
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"db": "not_configured", "status": "error"})

    def test_health_returns_503_for_unexpected_query_result(self):
        with patch("app.psycopg.connect") as connect:
            cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (0,)
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"db": "unexpected_result", "status": "error"})

    def test_configured_version_appears_in_api_and_footer(self):
        with patch.dict(app.config, {"APP_VERSION": "test-sha-012345"}):
            response = self.client.get("/api/info")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, {
                "service": "TaskFlow", "version": "test-sha-012345",
            })
            response = self.client.get("/projects")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"<code>test-sha-012345</code>", response.data)

    def test_metrics_expose_application_request_counter(self):
        self.client.get("/api/info")
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"taskflow_requests_total", response.data)
        self.assertIn(b"flask_http_request_duration_seconds", response.data)
