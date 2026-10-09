FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

COPY services/worker/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

COPY services/common/dorilab /app/dorilab
COPY packages/contracts /app/packages/contracts
COPY fixtures /app/fixtures

RUN useradd --uid 10001 --create-home dorilab && chown -R dorilab:dorilab /app
USER 10001
