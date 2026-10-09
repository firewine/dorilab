"""Local, file-based connection requests. No SSH key or Docker access in the app."""
from __future__ import annotations

import os
import re
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from .config import CONNECTION_CONFIG_PATH


CONTROL_PATH = CONNECTION_CONFIG_PATH.parent / "control"
LOCK_NAME = "dorilab.local-connection"
TERMINAL_PHASES = {"APPLIED", "FAILED"}


def enabled() -> bool:
    return os.getenv("DORILAB_LOCAL_CONNECTION_CONTROL") == "1"


def read_fields(name: str) -> dict[str, str]:
    try:
        lines = (CONTROL_PATH / name).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    # This channel never contains credentials, commands, or arbitrary messages.
    return dict(line.split("=", 1) for line in lines
                if re.fullmatch(r"[A-Z_]+=[A-Za-z0-9._:+-]*", line))


def controller_available() -> bool:
    try:
        age = time.time() - int(read_fields("heartbeat.env").get("UPDATED_AT", "0"))
    except ValueError:
        return False
    return enabled() and 0 <= age <= 15


def pending() -> bool:
    if not enabled():
        return False
    request = read_fields("request.env")
    if not request.get("REQUEST_ID"):
        return False
    result = read_fields("status.env")
    return not (result.get("REQUEST_ID") == request["REQUEST_ID"]
                and result.get("PHASE") in TERMINAL_PHASES)


def lock(cur) -> None:
    if enabled():
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_NAME,))


def projection() -> dict:
    result = read_fields("status.env")
    request = read_fields("request.env")
    phase = result.get("PHASE", "IDLE")
    if pending() and request.get("REQUEST_ID") != result.get("REQUEST_ID"):
        phase = "REQUESTED"
    return {
        "available": controller_available(),
        "phase": phase,
        "pending": pending(),
        "request_id": request.get("REQUEST_ID"),
        "code": result.get("CODE"),
        "ssh_state": result.get("SSH_STATE", "NOT_CONNECTED"),
        "applied_host": result.get("ACTIVE_HOST"),
        "applied_port": result.get("ACTIVE_PORT"),
        "updated_at": result.get("UPDATED_AT"),
    }


def request_apply(host: str, port: int) -> str:
    request_id = uuid4().hex
    CONTROL_PATH.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = (f"REQUEST_ID={request_id}\nRUNPOD_HOST={host}\n"
               f"RUNPOD_SSH_PORT={port}\nREQUESTED_AT={int(time.time())}\n")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONTROL_PATH,
                                         prefix=".request-", delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, CONTROL_PATH / "request.env")
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    return request_id
