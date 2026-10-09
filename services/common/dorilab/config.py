from __future__ import annotations

import os
import json
from pathlib import Path
from psycopg.conninfo import make_conninfo


def _secret(env_name: str, file_env_name: str, *, required: bool = True) -> str:
    direct = os.getenv(env_name)
    if direct is not None:
        return direct
    path = os.getenv(file_env_name)
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            if required:
                raise
    if required:
        raise RuntimeError(f"missing {env_name} or {file_env_name}")
    return ""


def db_password() -> str:
    return _secret("DORILAB_DB_PASSWORD", "DORILAB_DB_PASSWORD_FILE")


def session_secret() -> str:
    return _secret("DORILAB_SESSION_SECRET", "DORILAB_SESSION_SECRET_FILE")


def inference_token() -> str:
    return _secret("DORILAB_INFERENCE_TOKEN", "DORILAB_INFERENCE_TOKEN_FILE")


def database_url() -> str:
    connection_file = os.getenv("DORILAB_DB_CONNECTION_FILE")
    if connection_file:
        value = json.loads(Path(connection_file).read_text(encoding="utf-8"))
        required = {"host", "dbname", "user", "password", "sslmode", "sslrootcert", "channel_binding"}
        if (not isinstance(value, dict) or set(value) != required
                or any(not isinstance(v, str) or not v or any(c in v for c in '\r\n\0') for v in value.values())
                or value["sslmode"] != "verify-full" or value["channel_binding"] != "require"):
            raise RuntimeError("invalid external database connection contract")
        import re
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*\.neon\.tech',value["host"]):
            raise RuntimeError("invalid external database endpoint")
        return make_conninfo(**value, connect_timeout=15)
    host = os.getenv("DORILAB_DB_HOST", "db")
    port = int(os.getenv("DORILAB_DB_PORT", "5432"))
    name = os.getenv("DORILAB_DB_NAME", "dorilab")
    user = os.getenv("DORILAB_DB_USER", "dorilab")
    password = db_password()
    return make_conninfo(host=host, port=port, dbname=name, user=user, password=password)


ARTIFACT_ROOT = Path(os.getenv("DORILAB_ARTIFACT_ROOT", "/var/lib/dorilab/artifacts"))
EXPORT_ROOT = Path(os.getenv("DORILAB_EXPORT_ROOT", "/var/lib/dorilab/exports"))
CONNECTION_CONFIG_PATH = Path(os.getenv("DORILAB_CONNECTION_CONFIG_PATH", "/var/lib/dorilab/connection/runpod.env"))
KNOWN_HOSTS_PATH = Path(os.getenv("DORILAB_KNOWN_HOSTS_PATH", "/var/lib/dorilab/ssh/known_hosts"))
APP_MODE = os.getenv("DORILAB_MODE", "LIVE").upper()
MODEL_PROFILE = os.getenv("DORILAB_MODEL_PROFILE", "dorilab-source-review-v15-rc3")
INFERENCE_URL = os.getenv("DORILAB_INFERENCE_URL", "http://llm-tunnel:18080").rstrip("/")
