"""Small durable artifact adapter; filesystem remains the default.

The existing API checks project membership before resolving any path. This
module preserves its object keys and bytes; it does not grant business access.
Local files are an expendable cache in this mode, never the durable copy.
"""
import hashlib
import os
import tempfile
from pathlib import Path

from .db import connection


def enabled():
    value = os.getenv("DORILAB_ARTIFACT_BACKEND", "filesystem")
    if value not in {"filesystem", "postgres"}:
        raise RuntimeError("unsupported artifact backend")
    return value == "postgres"


def persist(namespace, object_key, data):
    sha = hashlib.sha256(data).hexdigest()
    limit = int(os.getenv("DORILAB_CLOUD_ARTIFACT_LIMIT_BYTES", str(64 * 1024 * 1024)))
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("file exceeds 20 MiB limit")
    with connection() as conn, conn.cursor() as cur:
        # Serialize quota admission across both namespaces and server processes.
        cur.execute("SELECT pg_advisory_xact_lock(73409152)")
        cur.execute("SELECT sha256,byte_size FROM cloud_artifact_objects WHERE namespace=%s AND object_key=%s",
                    (namespace,object_key))
        previous = cur.fetchone()
        if previous:
            if previous["sha256"] != sha or previous["byte_size"] != len(data):
                raise ValueError("immutable artifact key already has different bytes")
            return
        cur.execute("SELECT coalesce(sum(byte_size),0) AS bytes FROM cloud_artifact_objects")
        if cur.fetchone()["bytes"] + len(data) > limit:
            raise ValueError("cloud artifact storage quota exceeded")
        cur.execute("INSERT INTO cloud_artifact_objects(namespace,object_key,content,byte_size,sha256) VALUES (%s,%s,%s,%s,%s)",
                    (namespace,object_key,data,len(data),sha))


def materialize(namespace, object_key, destination: Path):
    # Re-check the durable receipt even if a cache exists. A corrupt local cache
    # is replaced only by hash-verified original bytes from the durable store.
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content,sha256,byte_size FROM cloud_artifact_objects WHERE namespace=%s AND object_key=%s",
                    (namespace,object_key))
        row = cur.fetchone()
    if not row:
        raise FileNotFoundError("durable artifact missing")
    data = bytes(row["content"])
    if len(data) != row["byte_size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("durable artifact integrity mismatch")
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == row["sha256"]:
        return destination
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cloud-",dir=destination.parent)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination
