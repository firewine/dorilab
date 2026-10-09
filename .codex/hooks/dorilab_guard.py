#!/usr/bin/env python3
"""Narrow PreToolUse guard for DoriLab.

This is deliberately not a shell sandbox or workflow engine. It blocks only a
small set of high-confidence commands that contradict explicit project boundaries.
Malformed or unfamiliar hook input fails open so routine development is not held
up by hook/runtime version drift.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


def deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def command_from(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command")
    return command if isinstance(command, str) else ""


def normalize(command: str) -> str:
    return " ".join(command.strip().split())


def destructive_reason(command: str) -> str | None:
    cmd = normalize(command)
    lower = cmd.lower()

    if re.search(r"(^|[;&|()]\s*)git\s+reset\s+--hard(?:\s|$)", lower):
        return "DoriLab guard: git reset --hard can discard user work"

    if re.search(
        r"(^|[;&|()]\s*)git\s+push\b[^\n]*(?:--force(?:-with-lease|-if-includes)?|-f\b|--mirror\b|--delete\b)",
        lower,
    ):
        return "DoriLab guard: remote history rewrite or ref deletion is outside normal development"

    clean = re.search(r"(^|[;&|()]\s*)git\s+clean\s+([^;&|]+)", lower)
    if clean:
        compact_flags = "".join(re.findall(r"-[a-z]+", clean.group(2)))
        if "f" in compact_flags and ("d" in compact_flags or "x" in compact_flags):
            return "DoriLab guard: forced git clean of directories or ignored files can remove local data"

    broad_rm = (
        r"(^|[;&|()]\s*)rm\s+-[^\s]*r[^\s]*f[^\s]*\s+/(?:\s|$)",
        r"(^|[;&|()]\s*)rm\s+-[^\s]*r[^\s]*f[^\s]*\s+~(?:/)?(?:\s|$)",
        r"(^|[;&|()]\s*)rm\s+-[^\s]*r[^\s]*f[^\s]*\s+\.(?:/)?(?:\s|$)",
        r"(^|[;&|()]\s*)rm\s+-[^\s]*r[^\s]*f[^\s]*\s+\.\.(?:/)?(?:\s|$)",
    )
    if any(re.search(pattern, lower) for pattern in broad_rm):
        return "DoriLab guard: broad recursive deletion of root, home, or workspace is blocked"

    if re.search(r"(^|[;&|()]\s*)docker\s+(?:system|volume|container|image|builder)\s+prune\b", lower):
        return "DoriLab guard: Docker prune can remove resources outside this Compose project"

    if re.search(r"(^|[;&|()]\s*)docker\s+compose\b[^;&|]*\bdown\b[^;&|]*(?:\s-v\b|--volumes\b)", lower):
        return "DoriLab guard: Compose volume deletion would remove the persistent development database"

    if re.search(r"(^|[;&|()]\s*)docker\s+volume\s+(?:rm|remove)\b", lower):
        return "DoriLab guard: direct Docker volume deletion is outside the preservation workflow"

    if re.search(r"(^|[;&|()]\s*)docker\s+context\s+use\b", lower):
        return "DoriLab guard: do not change the user's global Docker context"

    if re.search(r"(?:stricthostkeychecking\s*=\s*no|userknownhostsfile\s*=\s*/dev/null|forwardagent\s*=\s*yes)", lower):
        return "DoriLab guard: SSH host verification/agent-forwarding bypass is forbidden"

    # OpenSSH -A enables forwarding while lowercase -a disables it. Keep this
    # check case-sensitive so the safe disabling form is never blocked.
    if re.search(r"(^|[;&|()]\s*)ssh(?:\s|$)[^;&|]*(?<!\S)-A(?!\S)", cmd):
        return "DoriLab guard: SSH agent forwarding is disabled for RunPod connections"

    if re.search(r"(^|[;&|()]\s*)runpodctl\s+(?:stop|terminate|remove|delete)\b", lower):
        return "DoriLab guard: stopping or deleting a Pod requires separate explicit user direction"

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    reason = destructive_reason(command_from(payload))
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
