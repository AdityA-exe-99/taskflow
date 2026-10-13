from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_projects_name_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Task(db.Model):
    __tablename__ = "tasks"

    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_tasks_title_not_blank",
        ),
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')",
            name="ck_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_tasks_priority",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            name="fk_tasks_project_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="todo",
        server_default="todo",
    )
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="tasks")