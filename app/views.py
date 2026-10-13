import secrets

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import Project, Task
from .validation import (
    TASK_PRIORITIES,
    TASK_STATUSES,
    validate_project,
    validate_task,
)
from datetime import datetime, timezone

from sqlalchemy import func


ui = Blueprint("ui", __name__)


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@ui.context_processor
def template_helpers():
    return {"csrf_token": csrf_token}


@ui.before_request
def protect_form_submissions():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        expected = session.get("csrf_token", "")
        submitted = request.form.get("csrf_token", "")

        if not expected or not secrets.compare_digest(
            expected.encode("utf-8"),
            submitted.encode("utf-8"),
        ):
            abort(
                400,
                description=(
                    "This form could not be verified. "
                    "Go back, reload the page and try again."
                ),
            )


@ui.get("/projects")
def projects():
    statement = db.select(Project).order_by(
        Project.created_at.desc(),
        Project.id.desc(),
    )
    project_list = db.session.scalars(statement).all()

    return render_template(
        "projects.html",
        projects=project_list,
    )


@ui.route("/projects/new", methods=["GET", "POST"])
def create_project():
    values = {"name": "", "description": ""}
    errors = {}
    status_code = 200

    if request.method == "POST":
        values, errors = validate_project(request.form)

        if errors:
            status_code = 400
        else:
            project = Project(**values)
            db.session.add(project)

            try:
                db.session.commit()
            except SQLAlchemyError as error:
                db.session.rollback()
                current_app.logger.error(
                    "Project creation failed: %s",
                    type(error).__name__,
                )
                errors["form"] = (
                    "The project could not be saved. Please try again."
                )
                status_code = 503
            else:
                flash("Project created successfully.", "success")
                return redirect(url_for("ui.projects"), code=303)

    return render_template(
        "project_form.html",
        values=values,
        errors=errors,
    ), status_code
@ui.get("/projects/<int:project_id>")
def project_detail(project_id):
    project = db.get_or_404(Project, project_id)
    statement = (
        db.select(Task)
        .where(Task.project_id == project.id)
        .order_by(Task.created_at.desc(), Task.id.desc())
    )
    tasks = db.session.scalars(statement).all()

    return render_template(
        "project_detail.html",
        project=project,
        tasks=tasks,
        statuses=TASK_STATUSES,
        priorities=TASK_PRIORITIES,
    )


@ui.route("/projects/<int:project_id>/tasks/new", methods=["GET", "POST"])
def create_task(project_id):
    project = db.get_or_404(Project, project_id)
    values = {
        "title": "",
        "description": "",
        "status": "todo",
        "priority": "medium",
        "due_date": "",
    }
    errors = {}
    status_code = 200

    if request.method == "POST":
        values = {
            field: request.form.get(field, "").strip()
            for field in values
        }
        data, errors = validate_task(values)

        if errors:
            status_code = 400
        else:
            task = Task(project_id=project.id, **data)
            db.session.add(task)

            try:
                db.session.commit()
            except SQLAlchemyError as error:
                db.session.rollback()
                current_app.logger.error(
                    "Task creation failed: %s",
                    type(error).__name__,
                )
                errors["form"] = (
                    "The task could not be saved. Please try again."
                )
                status_code = 503
            else:
                flash("Task created successfully.", "success")
                return redirect(
                    url_for("ui.project_detail", project_id=project.id),
                    code=303,
                )

    return render_template(
        "task_form.html",
        project=project,
        values=values,
        errors=errors,
        statuses=TASK_STATUSES,
        priorities=TASK_PRIORITIES,
        page_title="Add task",
        submit_label="Create task",
        form_action=url_for("ui.create_task", project_id=project.id),
    ), status_code
def _get_project_task(project_id, task_id):
    project = db.get_or_404(Project, project_id)
    task = db.get_or_404(Task, task_id)

    if task.project_id != project.id:
        abort(404)

    return project, task


@ui.route(
    "/projects/<int:project_id>/tasks/<int:task_id>/edit",
    methods=["GET", "POST"],
)
def edit_task(project_id, task_id):
    project, task = _get_project_task(project_id, task_id)
    values = {
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else "",
    }
    errors = {}
    status_code = 200

    if request.method == "POST":
        values = {
            field: request.form.get(field, "").strip()
            for field in values
        }
        data, errors = validate_task(values)

        if errors:
            status_code = 400
        else:
            task.title = data["title"]
            task.description = data["description"]
            task.status = data["status"]
            task.priority = data["priority"]
            task.due_date = data["due_date"]

            try:
                db.session.commit()
            except SQLAlchemyError as error:
                db.session.rollback()
                current_app.logger.error(
                    "Task update failed: %s",
                    type(error).__name__,
                )
                errors["form"] = (
                    "The changes could not be saved. Please try again."
                )
                status_code = 503
            else:
                flash("Task updated successfully.", "success")
                return redirect(
                    url_for("ui.project_detail", project_id=project.id),
                    code=303,
                )

    return render_template(
        "task_form.html",
        project=project,
        values=values,
        errors=errors,
        statuses=TASK_STATUSES,
        priorities=TASK_PRIORITIES,
        page_title="Edit task",
        submit_label="Save changes",
        form_action=url_for(
            "ui.edit_task",
            project_id=project.id,
            task_id=task.id,
        ),
    ), status_code


@ui.route(
    "/projects/<int:project_id>/tasks/<int:task_id>/delete",
    methods=["GET", "POST"],
)
def delete_task(project_id, task_id):
    project, task = _get_project_task(project_id, task_id)
    error_message = None
    status_code = 200

    if request.method == "POST":
        try:
            db.session.delete(task)
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            current_app.logger.error(
                "Task deletion failed: %s",
                type(error).__name__,
            )
            error_message = (
                "The task could not be deleted. Please try again."
            )
            status_code = 503
        else:
            flash("Task deleted successfully.", "success")
            return redirect(
                url_for("ui.project_detail", project_id=project.id),
                code=303,
            )

    return render_template(
        "task_delete.html",
        project=project,
        task=task,
        error_message=error_message,
    ), status_code
@ui.get("/")
def dashboard():
    today = datetime.now(timezone.utc).date()

    project_count = db.session.scalar(
        db.select(func.count(Project.id))
    )

    status_counts = dict(
        db.session.execute(
            db.select(Task.status, func.count(Task.id))
            .group_by(Task.status)
        ).all()
    )

    overdue_count = db.session.scalar(
        db.select(func.count(Task.id)).where(
            Task.status != "done",
            Task.due_date < today,
        )
    )

    open_tasks = db.session.execute(
        db.select(Task, Project.name)
        .join(Project, Task.project_id == Project.id)
        .where(Task.status != "done")
        .order_by(
            Task.due_date.asc().nulls_last(),
            Task.id.asc(),
        )
        .limit(6)
    ).all()

    summary_cards = [
        ("Projects", project_count),
        ("Total tasks", sum(status_counts.values())),
        ("To do", status_counts.get("todo", 0)),
        ("In progress", status_counts.get("in_progress", 0)),
        ("Done", status_counts.get("done", 0)),
        ("Overdue", overdue_count),
    ]

    return render_template(
        "dashboard.html",
        today=today,
        summary_cards=summary_cards,
        open_tasks=open_tasks,
        statuses=TASK_STATUSES,
        priorities=TASK_PRIORITIES,
    )


@ui.route(
    "/projects/<int:project_id>/delete",
    methods=["GET", "POST"],
)
def delete_project(project_id):
    project = db.get_or_404(Project, project_id)
    project_name = project.name
    task_count = db.session.scalar(
        db.select(func.count(Task.id)).where(
            Task.project_id == project_id
        )
    )

    error_message = None
    status_code = 200

    if request.method == "POST":
        try:
            db.session.delete(project)
            db.session.commit()
        except SQLAlchemyError as error:
            db.session.rollback()
            current_app.logger.error(
                "Project deletion failed: %s",
                type(error).__name__,
            )
            error_message = (
                "The project could not be deleted. Please try again."
            )
            status_code = 503
        else:
            flash("Project deleted successfully.", "success")
            return redirect(url_for("ui.projects"), code=303)

    return render_template(
        "project_delete.html",
        project_id=project_id,
        project_name=project_name,
        task_count=task_count,
        error_message=error_message,
    ), status_code