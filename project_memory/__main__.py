"""Trusted local operator CLI; does not expose a memory HTTP service."""
import argparse
import json
from pathlib import Path
import sys

from . import AccessScope, MemoryStore
from .bridge import CONTRACT_ID, HTTPClient, generate, prepare
from .store import atomic_json, strict_loads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--project", required=True, help="Local operator-authorized project; not an untrusted HTTP grant")
    commands = parser.add_subparsers(dest="command", required=True)
    insert = commands.add_parser("insert")
    insert.add_argument("file", type=Path)
    insert.add_argument("--expected-version")
    commands.add_parser("manifest")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("trajectory_id")
    inspect.add_argument("--start", type=int, default=0)
    inspect.add_argument("--stop", type=int)
    withdraw = commands.add_parser("withdraw")
    withdraw.add_argument("trajectory_id")
    withdraw.add_argument("--expected-version", required=True)
    for name in ("query", "prepare", "generate"):
        command = commands.add_parser(name)
        command.add_argument("file", type=Path, help="SourceReview packet JSON; review_question and scope drive retrieval")
        command.add_argument("--top-k", type=int, default=6)
        command.add_argument("--max-bytes", type=int, default=12000)
        command.add_argument("--queries-file", type=Path, help='Optional pool queries: {"raw":"...","events":"...","notes":"..."}')
        command.add_argument("--controller", choices=["off", "rules", "qwen"], default="qwen")
        command.add_argument("--planner-url", default="http://127.0.0.1:8080")
        command.add_argument("--planner-token-file", type=Path, default=Path('/root/.config/dorilab/inference.token'))
        command.add_argument("--planner-trace-dir", type=Path, help="New directory for Qwen plan input/output receipts")
        command.add_argument("--controller-timeout", type=float, default=90)
        if name != "query":
            command.add_argument("--contract-id", default=CONTRACT_ID)
            command.add_argument("--max-new-tokens", type=int, default=384)
            command.add_argument("--native-check", action="store_true", help="RunPod only: load CPU processor, never model")
        if name == "prepare":
            command.add_argument("--output", type=Path, required=True)
        if name == "generate":
            command.add_argument("--base-url", default="http://127.0.0.1:8080")
            command.add_argument("--token-file", type=Path, required=True)
            command.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    store = MemoryStore(args.store, AccessScope(frozenset({args.project})))
    if args.command == "insert":
        result = store.insert(args.project, strict_loads(args.file.read_text()), expected_version=args.expected_version)
    elif args.command == "manifest":
        result = store.manifest(args.project)
    elif args.command == "inspect":
        result = store.inspect(args.project, args.trajectory_id, args.start, args.stop)
    elif args.command == "withdraw":
        result = {"version": store.withdraw(args.project, args.trajectory_id, expected_version=args.expected_version)}
    else:
        packet = strict_loads(args.file.read_text())
        queries = strict_loads(args.queries_file.read_text()) if args.queries_file else None
        options = dict(queries=queries, top_k=args.top_k, max_bytes=args.max_bytes)
        controller = None
        if args.controller != "off":
            from .controller import SearchController, QwenPlanner
            planner = None
            if args.controller == "qwen":
                import uuid
                trace_dir = args.planner_trace_dir or args.store / '_planner_traces' / uuid.uuid4().hex
                planner = QwenPlanner(HTTPClient(args.planner_url, args.planner_token_file.read_text()), trace_dir)
            controller = SearchController(planner, timeout=args.controller_timeout)
        if args.command == "query":
            if controller:
                result = controller.gather(store, args.project, packet["review_question"], packet["scope"], **options)
            else:
                result = store.query(args.project, packet["review_question"], packet["scope"], **options)
        else:
            counter = None
            if args.native_check:
                # Reuse sealed native rendering; this path does not call runtime.load().
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "inference"))
                from model_runtime import ModelRuntime, processor
                runtime = ModelRuntime("memory-cpu-token-check", Path("/tmp"))
                runtime.proc, _ = processor()
                counter = lambda cid, user, limit: len(runtime.prepare(cid, user, limit)["ids"])
            preparation = prepare(store, args.project, packet, contract_id=args.contract_id,
                                  max_new_tokens=args.max_new_tokens, token_counter=counter, controller=controller, **options)
            if args.command == "prepare":
                if args.output.exists():
                    raise ValueError("output already exists")
                atomic_json(args.output, preparation)
                result = preparation["receipt"]
            else:
                client = HTTPClient(args.base_url, args.token_file.read_text())
                result = generate(store, args.project, preparation, client, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
