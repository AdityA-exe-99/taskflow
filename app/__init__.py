import os

import psycopg
from flask import Flask, jsonify, request
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy.engine import make_url

from .extensions import db, migrate
from . import models  # Register the models for database migrations.
from .views import ui


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["APP_VERSION"] = os.environ.get("APP_VERSION", "local")

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL must be configured.")

sqlalchemy_url = make_url(database_url)
if sqlalchemy_url.drivername in {"postgres", "postgresql"}:
    sqlalchemy_url = sqlalchemy_url.set(drivername="postgresql+psycopg")

app.config["SQLALCHEMY_DATABASE_URI"] = sqlalchemy_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "connect_args": {"connect_timeout": 3},
}

db.init_app(app)
migrate.init_app(app, db)
app.register_blueprint(ui)

metrics = PrometheusMetrics(app, group_by="endpoint")


@app.get("/api/info")
def index():
    return jsonify(
        service="TaskFlow",
        version=app.config["APP_VERSION"],
    )


@app.get("/health")
def health():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        return jsonify(status="error", db="not_configured"), 503

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=3,
            options="-c statement_timeout=3000",
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()

        if result != (1,):
            return jsonify(status="error", db="unexpected_result"), 503

    except psycopg.Error:
        app.logger.warning("Database health check failed")
        return jsonify(status="error", db="unavailable"), 503

    return jsonify(status="ok", db="ok"), 200


metrics.register_default(
    metrics.counter(
        "taskflow_requests_total",
        "Request count by endpoint, method and status",
        labels={
            "endpoint": lambda: request.endpoint or "unmatched",
            "method": lambda: request.method,
            "status": lambda response: str(response.status_code),
        },
    )
)