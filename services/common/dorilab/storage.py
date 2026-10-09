from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import UUID

from .config import ARTIFACT_ROOT, EXPORT_ROOT
from . import cloud_storage


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def write_stream(project_id: UUID, artifact_id: UUID, stream) -> tuple[str, int, str]:
    directory = ARTIFACT_ROOT / str(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / str(artifact_id)
    temporary = directory / f".{artifact_id}.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with temporary.open("xb") as target:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ValueError("file exceeds 20 MiB limit")
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if cloud_storage.enabled():
            cloud_storage.persist("artifacts", str(final.relative_to(ARTIFACT_ROOT)), temporary.read_bytes())
        temporary.replace(final)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return str(final.relative_to(ARTIFACT_ROOT)), size, digest.hexdigest()


def write_bytes(project_id: UUID, artifact_id: UUID, data: bytes) -> tuple[str, int, str]:
    from io import BytesIO

    return write_stream(project_id, artifact_id, BytesIO(data))


def resolved_path(object_key: str) -> Path:
    candidate = (ARTIFACT_ROOT / object_key).resolve()
    root = ARTIFACT_ROOT.resolve()
    if root not in candidate.parents:
        raise ValueError("invalid object key")
    if cloud_storage.enabled():
        return cloud_storage.materialize("artifacts",object_key,candidate)
    return candidate


def write_export(project_id: UUID, export_id: UUID, data: bytes) -> tuple[str, int, str]:
    directory = EXPORT_ROOT / str(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"{export_id}.md"
    temporary = directory / f".{export_id}.part"
    try:
        with temporary.open("xb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        if cloud_storage.enabled():
            cloud_storage.persist("exports", str(final.relative_to(EXPORT_ROOT)), data)
        temporary.replace(final)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return str(final.relative_to(EXPORT_ROOT)), len(data), hashlib.sha256(data).hexdigest()


def resolved_export_path(object_key: str) -> Path:
    candidate = (EXPORT_ROOT / object_key).resolve()
    root = EXPORT_ROOT.resolve()
    if root not in candidate.parents:
        raise ValueError("invalid export object key")
    if cloud_storage.enabled():
        return cloud_storage.materialize("exports",object_key,candidate)
    return candidate
