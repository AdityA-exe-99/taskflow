from datetime import date
def validate_project(form):
    values = {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip(),
    }
    errors = {}

    if not values["name"]:
        errors["name"] = "Enter a project name."
    elif len(values["name"]) > 120:
        errors["name"] = "Use 120 characters or fewer."
    elif "\x00" in values["name"]:
        errors["name"] = "Remove the unsupported character from the name."

    if len(values["description"]) > 2000:
        errors["description"] = "Use 2,000 characters or fewer."
    elif "\x00" in values["description"]:
        errors["description"] = (
            "Remove the unsupported character from the description."
        )

    return values, errors
TASK_STATUSES = {
    "todo": "To do",
    "in_progress": "In progress",
    "done": "Done",
}
TASK_PRIORITIES = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}


def validate_task(form):
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "status": form.get("status", "").strip(),
        "priority": form.get("priority", "").strip(),
        "due_date": None,
    }
    errors = {}

    if not data["title"]:
        errors["title"] = "Enter a task title."
    elif len(data["title"]) > 200:
        errors["title"] = "Use 200 characters or fewer."
    elif "\x00" in data["title"]:
        errors["title"] = "Remove the unsupported character from the title."

    if len(data["description"]) > 2000:
        errors["description"] = "Use 2,000 characters or fewer."
    elif "\x00" in data["description"]:
        errors["description"] = (
            "Remove the unsupported character from the description."
        )

    if data["status"] not in TASK_STATUSES:
        errors["status"] = "Choose a valid status."

    if data["priority"] not in TASK_PRIORITIES:
        errors["priority"] = "Choose a valid priority."

    raw_date = form.get("due_date", "").strip()
    if raw_date:
        try:
            parsed_date = date.fromisoformat(raw_date)
            if parsed_date.isoformat() != raw_date:
                raise ValueError
            data["due_date"] = parsed_date
        except ValueError:
            errors["due_date"] = "Enter a valid date in YYYY-MM-DD format."

    return data, errors