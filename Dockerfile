FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt

RUN groupadd --system taskflow \
    && useradd --system --gid taskflow taskflow

COPY --chown=taskflow:taskflow app ./app
COPY --chown=taskflow:taskflow migrations ./migrations
COPY --chown=taskflow:taskflow docker-entrypoint.py ./docker-entrypoint.py

USER taskflow

EXPOSE 8000

ENTRYPOINT ["python", "/app/docker-entrypoint.py"]

CMD ["gunicorn", "--no-control-socket", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]