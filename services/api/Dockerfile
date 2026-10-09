FROM python:3.12.7-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

COPY services/common/dorilab /app/dorilab
COPY migrations /app/migrations
COPY packages/contracts /app/packages/contracts
COPY apps/web /app/apps/web
COPY mockup /app/mockup
COPY fixtures /app/fixtures
COPY compose.yaml /app/compose.yaml

RUN useradd --uid 10001 --create-home dorilab && chown -R dorilab:dorilab /app
USER 10001

EXPOSE 8000
