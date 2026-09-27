"""Bounded, file-backed memory for a single host; no database or model dependency.

Immutable trajectory revisions live in an atomically replaced project snapshot.
Local flock serializes writers. This is NOT a distributed/network-volume lock.
Callers authenticate outside this module and supply a trusted AccessScope.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading

SCHEMA = "dorilab.project-memory.v1"
POOLS = ("raw", "events", "notes")
MAX_STATE_BYTES = 32 * 1024 * 1024
MAX_REVISIONS = 1000
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$")
SCOPE_KEYS = {"unit_id", "configuration_id", "run_id"}
FORBIDDEN = {"gold", "expected", "rationale", "rationale_ko", "reference_answer",
             "sufficient_sets", "acceptable_reason_codes", "reference_requirement",
             "training_eligible", "supporting_fact_ids", "supporting_observation_ids"}


class MemoryError(ValueError):
    pass


class ConflictError(MemoryError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_loads(text):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise MemoryError("duplicate JSON key")
            result[k] = v
        return result
    def constant(_):
        raise MemoryError("nonfinite JSON value")
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    validate_content(value)
    return value


def validate_content(value):
    if isinstance(value, dict):
        if FORBIDDEN.intersection(value):
            raise MemoryError("answer metadata is not memory evidence")
        for v in value.values():
            validate_content(v)
    elif isinstance(value, list):
        for v in value:
            validate_content(v)
    elif isinstance(value, str):
        if any(t in value for t in ("<|im_start|>", "<|im_end|>", "<|endoftext|>")):
            raise MemoryError("reserved chat delimiter")
    elif isinstance(value, float) and not math.isfinite(value):
        raise MemoryError("nonfinite number")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value) or ".." in value:
        raise MemoryError("invalid identifier")
    return value


def text_field(value, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise MemoryError("invalid or oversized text")
    return value


def timestamp(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise MemoryError("timestamp must be ISO-8601 with timezone") from error
    if date.tzinfo is None:
        raise MemoryError("timestamp needs timezone")
    return date.astimezone(timezone.utc)


def validate_scope(scope):
    if not isinstance(scope, dict) or set(scope) != SCOPE_KEYS:
        raise MemoryError("exact unit/configuration/run scope required")
    for value in scope.values():
        text_field(value, 128)


def validate_trajectory(value):
    validate_content(value)
    if not isinstance(value, dict) or set(value) != {"trajectory_id", "source", "scope", "steps", "notes"}:
        raise MemoryError("invalid trajectory fields")
    identifier(value["trajectory_id"])
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"uri", "revision"}:
        raise MemoryError("source uri and revision required")
    text_field(source["uri"], 1024)
    text_field(source["revision"], 128)
    validate_scope(value["scope"])
    steps = value["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise MemoryError("trajectory must have 1..100 steps")
    previous = None
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"observed_at", "observation", "action"}:
            raise MemoryError("invalid step fields")
        date = timestamp(step["observed_at"])
        if previous is not None and date < previous:
            raise MemoryError("steps must be in temporal order")
        previous = date
        text_field(step["observation"])
        if not isinstance(step["action"], str) or len(step["action"]) > 2000:
            raise MemoryError("invalid action; use empty string if none")
    notes = value["notes"]
    if not isinstance(notes, list) or len(notes) > 30:
        raise MemoryError("too many notes")
    for note in notes:
        if not isinstance(note, dict) or set(note) != {"kind", "text", "status", "step_indices"}:
            raise MemoryError("invalid note fields")
        if note["kind"] not in {"workflow", "gotcha", "premise"} or note["status"] not in {"candidate", "confirmed"}:
            raise MemoryError("invalid note kind or status")
        text_field(note["text"], 4000)
        indices = note["step_indices"]
        if not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(steps) for i in indices):
            raise MemoryError("note must reference existing steps")
        if len(indices) != len(set(indices)):
            raise MemoryError("duplicate note reference")
    if len(canonical(value).encode()) > 512 * 1024:
        raise MemoryError("trajectory exceeds 512 KiB")


@dataclass(frozen=True)
class AccessScope:
    """Trusted grant supplied by application/operator, never from an HTTP body."""
    projects: frozenset[str]

    def check(self, project):
        identifier(project)
        if project not in self.projects:
            raise PermissionError("project access denied")


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (canonical(value) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".memory-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        # Some network filesystems do not support directory fsync. Do not claim
        # power-loss durability beyond the filesystem's guarantees.
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def terms(text):
    words = re.findall(r"[a-z0-9_]+|[가-힣]+", text.lower())
    result = list(words)
    for word in words:
        if re.fullmatch(r"[가-힣]+", word) and len(word) > 2:
            result.extend(word[i:i+2] for i in range(len(word)-1))
    return result


def rank(records, query):
    """BM25 lexical baseline; no claim of dense/LLM retrieval equivalence."""
    wanted = set(terms(query))
    counts = [Counter(terms(r["text"])) for r in records]
    average = sum(sum(c.values()) for c in counts) / max(1, len(counts)) or 1
    df = Counter(t for c in counts for t in c)
    scored = []
    for record, c in zip(records, counts):
        length = sum(c.values())
        score = sum(math.log(1 + (len(records)-df[t]+0.5)/(df[t]+0.5)) *
                    (c[t]*2.2)/(c[t]+1.2*(0.25+0.75*length/average))
                    for t in wanted if c[t])
        if score > 0:
            scored.append((score, record))
    return sorted(scored, key=lambda x: (-x[0], x[1]["evidence_id"]))


class MemoryStore:
    def __init__(self, root, access, *, cache_size=64):
        if type(cache_size) is not int or not 0 <= cache_size <= 1024:
            raise MemoryError("cache size must be 0..1024")
        self.root = Path(root).resolve()
        self.access = access
        self.cache_size = cache_size
        self.cache = OrderedDict()
        self.cache_lock = threading.RLock()

    def _directory(self, project):
        self.access.check(project)
        path = self.root / project
        if path.is_symlink() or path.resolve().parent != self.root:
            raise MemoryError("project path escapes store")
        return path

    @contextmanager
    def _writer(self, project):
        directory = self._directory(project)
        directory.mkdir(parents=True, exist_ok=True)
        locks = Path(tempfile.gettempdir()) / ("dorilab-memory-locks-" + str(os.getuid()))
        locks.mkdir(mode=0o700, exist_ok=True)
        if locks.is_symlink() or locks.stat().st_uid != os.getuid() or locks.stat().st_mode & 0o077:
            raise MemoryError("unsafe local lock directory")
        key = digest([str(self.root), project])
        fd = os.open(locks / key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def _read(self, project):
        path = self._directory(project) / "state.json"
        if path.is_symlink():
            raise MemoryError("state symlink forbidden")
        if not path.exists():
            state = dict(schema=SCHEMA, project_id=project, sequence=0, revisions=[], active={})
            return dict(state, version=digest(state))
        if path.stat().st_size > MAX_STATE_BYTES:
            raise MemoryError("store exceeds capacity")
        state = strict_loads(path.read_text())
        check = dict(state)
        version = check.pop("version", None)
        if state.get("schema") != SCHEMA or state.get("project_id") != project or digest(check) != version:
            raise MemoryError("snapshot integrity check failed")
        return state

    def _commit(self, project, state):
        state.pop("version", None)
        state["sequence"] += 1
        state["version"] = digest(state)
        if len(canonical(state).encode()) + 1 > MAX_STATE_BYTES or len(state["revisions"]) > MAX_REVISIONS:
            raise MemoryError("project memory capacity reached")
        atomic_json(self._directory(project) / "state.json", state)
        return state["version"]

    def insert(self, project, trajectory, *, expected_version=None):
        self.access.check(project)
        trajectory = deepcopy(trajectory)
        validate_trajectory(trajectory)
        content_hash = digest(trajectory)
        with self._writer(project):
            state = self._read(project)
            if expected_version is not None and expected_version != state["version"]:
                raise ConflictError("memory changed; refresh snapshot")
            tid = trajectory["trajectory_id"]
            old = state["active"].get(tid)
            if old == content_hash:
                return dict(version=state["version"], duplicate=True, source_hash=content_hash)
            if old is not None and expected_version is None:
                raise ConflictError("replacement requires expected_version")
            revisions = [r for r in state["revisions"] if r["trajectory"]["trajectory_id"] == tid]
            if any(r["trajectory"]["source"]["revision"] == trajectory["source"]["revision"] for r in revisions):
                raise ConflictError("source revision already recorded; use a new revision")
            state["revisions"].append(dict(source_hash=content_hash, trajectory=trajectory))
            state["active"][tid] = content_hash
            version = self._commit(project, state)
        return dict(version=version, duplicate=False, source_hash=content_hash)

    def withdraw(self, project, trajectory_id, *, expected_version):
        identifier(trajectory_id)
        with self._writer(project):
            state = self._read(project)
            if expected_version != state["version"]:
                raise ConflictError("memory changed; refresh snapshot")
            if trajectory_id not in state["active"]:
                raise MemoryError("unknown active trajectory")
            del state["active"][trajectory_id]
            return self._commit(project, state)

    @staticmethod
    def _records(project, revision):
        trajectory = revision["trajectory"]
        source_hash = revision["source_hash"]
        common = dict(project_id=project, trajectory_id=trajectory["trajectory_id"],
                      scope=trajectory["scope"], source=trajectory["source"], source_hash=source_hash)
        def record(pool, index, text, spans, **extra):
            eid = "MEM-" + digest([project, source_hash, pool, index])[:32]
            return dict(common, evidence_id=eid, pool=pool, text=text, step_indices=spans, **extra)
        rows = []
        steps = trajectory["steps"]
        for i, step in enumerate(steps):
            rows.append(record("raw", i, step["observation"], [i], observed_at=step["observed_at"]))
            if i + 1 < len(steps) and step["action"] and step["observation"] != steps[i+1]["observation"]:
                after = steps[i+1]
                text = ("Recorded transition; temporal sequence does not establish causation.\n"
                        f"Before ({step['observed_at']}): {step['observation']}\n"
                        f"Action: {step['action']}\nAfter ({after['observed_at']}): {after['observation']}")
                rows.append(record("events", i, text, [i, i+1], observed_at=after["observed_at"]))
        for i, note in enumerate(trajectory["notes"]):
            if note["status"] == "confirmed":
                rows.append(record("notes", i, note["text"], note["step_indices"],
                                   kind=note["kind"], status="confirmed"))
        return rows

    def manifest(self, project):
        state = self._read(project)
        rows = []
        for revision in state["revisions"]:
            t = revision["trajectory"]
            if state["active"].get(t["trajectory_id"]) == revision["source_hash"]:
                records = self._records(project, revision)
                rows.append(dict(trajectory_id=t["trajectory_id"], source=t["source"], scope=t["scope"],
                                 source_hash=revision["source_hash"], steps=len(t["steps"]),
                                 pools=dict(Counter(r["pool"] for r in records))))
        return dict(schema=SCHEMA, project_id=project, version=state["version"],
                    sequence=state["sequence"], active_trajectories=rows,
                    retained_revisions=len(state["revisions"]))

    def inspect(self, project, trajectory_id, start=0, stop=None):
        state = self._read(project)
        source_hash = state["active"].get(identifier(trajectory_id))
        for revision in state["revisions"]:
            if revision["source_hash"] == source_hash:
                trajectory = revision["trajectory"]
                stop = len(trajectory["steps"]) if stop is None else stop
                if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= len(trajectory["steps"]):
                    raise MemoryError("invalid state span")
                return deepcopy(dict(project_id=project, version=state["version"], source_hash=source_hash,
                                     source=trajectory["source"], scope=trajectory["scope"],
                                     trajectory_id=trajectory_id, start=start, stop=stop,
                                     steps=trajectory["steps"][start:stop]))
        raise MemoryError("unknown active trajectory")

    def query(self, project, question, scope, *, queries=None, top_k=6, max_bytes=12000):
        self.access.check(project)  # Always before reading or cache lookup.
        text_field(question, 4000)
        validate_scope(scope)
        if type(top_k) is not int or not 1 <= top_k <= 30 or type(max_bytes) is not int or not 256 <= max_bytes <= 50000:
            raise MemoryError("invalid retrieval bounds")
        queries = {pool: question for pool in POOLS} if queries is None else queries
        if not isinstance(queries, dict) or not queries or set(queries) - set(POOLS):
            raise MemoryError("invalid retrieval streams")
        for value in queries.values():
            text_field(value, 4000)
        state = self._read(project)  # Observe mutations made by other local processes.
        key = digest([project, state["version"], question, scope, queries, top_k, max_bytes])
        with self.cache_lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                hit = deepcopy(self.cache[key])
                hit["cache_hit"] = True
                return hit
        records = []
        for revision in state["revisions"]:
            t = revision["trajectory"]
            if state["active"].get(t["trajectory_id"]) == revision["source_hash"] and t["scope"] == scope:
                records.extend(self._records(project, revision))
        streams = {pool: rank([r for r in records if r["pool"] == pool], query) for pool, query in queries.items()}
        # Round robin preserves streams instead of letting raw slices drown out notes.
        ordered = []
        for i in range(max((len(v) for v in streams.values()), default=0)):
            for pool in POOLS:
                if i < len(streams.get(pool, [])):
                    score, row = streams[pool][i]
                    ordered.append(dict(row, score=round(score, 6)))
        selected, excluded, size = [], [], 2
        for row in ordered:
            cost = len(canonical(row).encode()) + (1 if selected else 0)
            reason = "top_k" if len(selected) >= top_k else "byte_budget" if size + cost > max_bytes else None
            if reason:
                excluded.append(dict(evidence_id=row["evidence_id"], reason=reason))
            else:
                selected.append(row)
                size += cost
        result = dict(schema=SCHEMA, project_id=project, version=state["version"], question=question,
                      scope=deepcopy(scope), evidence=selected, excluded=excluded, evidence_bytes=size,
                      status="evidence_found" if selected else "no_evidence", cache_hit=False,
                      retriever="bm25-korean-bigrams-v1", streams=list(queries),
                      selection_policy="whole-records-round-robin; no text truncation")
        result["bundle_hash"] = digest({k: v for k, v in result.items() if k != "cache_hit"})
        with self.cache_lock:
            self.cache[key] = deepcopy(result)
            while len(self.cache) > self.cache_size:
                self.cache.popitem(last=False)
        return result
