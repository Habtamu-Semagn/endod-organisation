# TenaCare organisation portal API. Build from backend/:
#   docker build -t endod-organisation-api backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ORG_RECEIPTS_DIR=/data/receipts
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
# The code stays owned by root: the app user can read it, not change it.
# Only the receipts directory (a volume in deploy/docker-compose.yml) is
# writable; a new volume takes this ownership when it is first mounted.
RUN useradd --create-home --uid 10004 endodorg \
    && mkdir -p /data/receipts && chown endodorg:endodorg /data/receipts && chmod 700 /data/receipts
USER endodorg
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# Migrations run before the API starts, as the database owner, from the one-shot
# `migrate` service (deploy/docker-compose.yml: `alembic upgrade head`); the API
# itself connects as a role that cannot change the schema.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
