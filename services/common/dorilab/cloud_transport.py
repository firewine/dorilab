"""Explicit cloud transport configuration; readiness never controls app startup."""
import os
import re
from pathlib import Path


RUNPOD_HTTPS_ORIGIN = re.compile(r"https://[a-z0-9]{1,64}-19124\.proxy\.runpod\.net\Z")


def validate_cloud_mode() -> str:
    mode = os.getenv("DORILAB_MODE", "DEMO").upper()
    if mode == "DEMO":
        return mode
    if mode != "LIVE":
        raise RuntimeError("unsupported cloud execution mode")
    # Accept only the previously approved HTTPS bridge. No arbitrary target,
    # redirect, public inference TCP port, or SSH key is needed on this host.
    origin = os.getenv("DORILAB_INFERENCE_URL", "")
    if not RUNPOD_HTTPS_ORIGIN.fullmatch(origin):
        raise RuntimeError("cloud LIVE requires an approved RunPod HTTPS origin")
    token_path = os.getenv("DORILAB_INFERENCE_TOKEN_FILE", "")
    if not token_path:
        raise RuntimeError("cloud LIVE requires an inference token file")
    try:
        token = Path(token_path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        raise RuntimeError("cloud inference token file is unavailable") from None
    if not token or any(char.isspace() for char in token):
        raise RuntimeError("cloud inference token file is invalid")
    if os.getenv("DORILAB_INFERENCE_TOKEN") is not None:
        raise RuntimeError("cloud inference token must use the configured file")
    # This checks configuration only. A stopped GPU must not stop historical
    # reads, document downloads, or human decisions in the business API.
    return mode
