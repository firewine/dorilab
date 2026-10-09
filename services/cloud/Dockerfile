FROM python:3.12.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app
RUN apt-get update && apt-get install --no-install-recommends -y ca-certificates openssh-client && rm -rf /var/lib/apt/lists/*
COPY services/cloud/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY services/common/dorilab /app/dorilab
COPY migrations /app/migrations
COPY packages/contracts /app/packages/contracts
COPY apps/web /app/apps/web
COPY fixtures/demo /app/fixtures/demo
COPY mockup/DoriLab_SE_Workbench.html mockup/DoriLab_Final_Goal_KASA_ECSS_NASA.md /app/mockup/
RUN groupadd --gid 1000 secrets && useradd --uid 10001 --create-home --groups secrets dorilab && chown -R dorilab:dorilab /app
USER 10001
ENV DORILAB_ARTIFACT_BACKEND=postgres DORILAB_ARTIFACT_ROOT=/tmp/dorilab/artifacts DORILAB_EXPORT_ROOT=/tmp/dorilab/exports DORILAB_MODE=DEMO
EXPOSE 8000
CMD ["python","-m","dorilab.cloud_service"]
