import unittest
from datetime import date

from app.validation import validate_project, validate_task


def valid_task(**changes):
    form = {
        "title": "Prepare release",
        "description": "",
        "status": "todo",
        "priority": "medium",
        "due_date": "",
    }
    form.update(changes)
    return form


class ProjectValidationTests(unittest.TestCase):
    def test_project_whitespace_is_trimmed(self):
        data, errors = validate_project({
            "name": "  AeroDeploy  ",
            "description": "  Team project  ",
        })
        self.assertEqual(errors, {})
        self.assertEqual(data, {
            "name": "AeroDeploy",
            "description": "Team project",
        })

    def test_project_name_is_required(self):
        for name in ("", "   ", "\t\n"):
            with self.subTest(name=name):
                _, errors = validate_project({"name": name})
                self.assertEqual(set(errors), {"name"})

    def test_project_name_length_boundary(self):
        for length, accepted in ((120, True), (121, False)):
            with self.subTest(length=length):
                _, errors = validate_project({"name": "x" * length})
                self.assertEqual("name" not in errors, accepted)

    def test_project_description_length_boundary(self):
        for length, accepted in ((2000, True), (2001, False)):
            with self.subTest(length=length):
                _, errors = validate_project({
                    "name": "AeroDeploy",
                    "description": "x" * length,
                })
                self.assertEqual("description" not in errors, accepted)

    def test_project_null_characters_are_rejected(self):
        for field in ("name", "description"):
            with self.subTest(field=field):
                form = {"name": "AeroDeploy", "description": ""}
                form[field] = "bad\x00value"
                _, errors = validate_project(form)
                self.assertEqual(set(errors), {field})


class TaskValidationTests(unittest.TestCase):
    def test_all_status_and_priority_combinations(self):
        for status in ("todo", "in_progress", "done"):
            for priority in ("low", "medium", "high"):
                with self.subTest(status=status, priority=priority):
                    data, errors = validate_task(valid_task(
                        status=status, priority=priority,
                    ))
                    self.assertEqual(errors, {})
                    self.assertEqual(data["status"], status)
                    self.assertEqual(data["priority"], priority)

    def test_task_whitespace_is_trimmed_without_changing_input(self):
        form = valid_task(
            title="  Prepare release  ",
            description="  Check health  ",
            status=" in_progress ",
            priority=" high ",
            due_date=" 2026-10-19 ",
        )
        original = form.copy()
        data, errors = validate_task(form)
        self.assertEqual(errors, {})
        self.assertEqual(data, {
            "title": "Prepare release",
            "description": "Check health",
            "status": "in_progress",
            "priority": "high",
            "due_date": date(2026, 10, 19),
        })
        self.assertEqual(form, original)

    def test_task_title_is_required(self):
        for title in ("", "   ", "\t\n"):
            with self.subTest(title=title):
                _, errors = validate_task(valid_task(title=title))
                self.assertEqual(set(errors), {"title"})

    def test_task_title_length_boundary(self):
        for length, accepted in ((200, True), (201, False)):
            with self.subTest(length=length):
                _, errors = validate_task(valid_task(title="x" * length))
                self.assertEqual("title" not in errors, accepted)

    def test_task_description_length_boundary(self):
        for length, accepted in ((2000, True), (2001, False)):
            with self.subTest(length=length):
                _, errors = validate_task(valid_task(
                    description="x" * length,
                ))
                self.assertEqual("description" not in errors, accepted)

    def test_task_null_characters_are_rejected(self):
        for field in ("title", "description"):
            with self.subTest(field=field):
                _, errors = validate_task(valid_task(
                    **{field: "bad\x00value"}
                ))
                self.assertEqual(set(errors), {field})

    def test_invalid_status_and_priority_are_rejected(self):
        cases = (
            ("status", ""),
            ("status", "finished"),
            ("status", "DONE"),
            ("priority", ""),
            ("priority", "urgent"),
            ("priority", "HIGH"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                _, errors = validate_task(valid_task(**{field: value}))
                self.assertEqual(set(errors), {field})

    def test_due_date_is_optional(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                data, errors = validate_task(valid_task(due_date=value))
                self.assertEqual(errors, {})
                self.assertIsNone(data["due_date"])

    def test_valid_dates_include_past_dates_and_leap_days(self):
        cases = (
            ("2000-01-01", date(2000, 1, 1)),
            ("2026-10-19", date(2026, 10, 19)),
            ("2028-02-29", date(2028, 2, 29)),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                data, errors = validate_task(valid_task(due_date=value))
                self.assertEqual(errors, {})
                self.assertEqual(data["due_date"], expected)

    def test_invalid_dates_and_formats_are_rejected(self):
        cases = (
            "2026-02-29",
            "2026-04-31",
            "2026-13-01",
            "19/10/2026",
            "20261019",
            "2026-W43-1",
            "2026-10-19T00:00:00",
            "not-a-date",
        )
        for value in cases:
            with self.subTest(value=value):
                data, errors = validate_task(valid_task(due_date=value))
                self.assertEqual(set(errors), {"due_date"})
                self.assertIsNone(data["due_date"])
