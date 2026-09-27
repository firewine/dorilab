from __future__ import annotations
import argparse
import json
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tools.common import ROOT, sha256, write_json


def is_expected_file(path: Path, fmt: str) -> bool:
    with path.open("rb") as f:
        head = f.read(1024)
    if fmt == "pdf":
        return b"%PDF-" in head
    if fmt == "pptx":
        try:
            with zipfile.ZipFile(path) as z:
                return "[Content_Types].xml" in z.namelist() and "ppt/presentation.xml" in z.namelist()
        except zipfile.BadZipFile:
            return False
    return False


def acquire(source: dict, dest_dir: Path) -> dict:
    sid, fmt = source["source_id"], source["native_format"]
    dest = dest_dir / f"{sid}__{Path(source['native_filename']).name}"
    event = {"source_id": sid, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
             "landing_url": source["landing_url"], "planned_split": source["planned_split"],
             "status": "FAILED", "sha256": None, "errors": []}
    if dest.is_file() and is_expected_file(dest, fmt):
        event.update(status="PRESENT_VALID_SIGNATURE", path=str(dest.relative_to(ROOT)),
                     sha256=sha256(dest), size_bytes=dest.stat().st_size)
        return event
    if dest.exists():
        event["errors"].append("An existing file has an unexpected signature; rename it before retrying.")
        return event
    for url in source["download_urls"]:
        for attempt in range(2):
            part = dest.with_suffix(dest.suffix + ".part")
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "DoriLab-SourceAcquisition/0.1 (research reference download)",
                    "Accept": "application/pdf, application/vnd.openxmlformats-officedocument.presentationml.presentation, */*",
                })
                with urllib.request.urlopen(req, timeout=60) as response:
                    content_type = response.headers.get("Content-Type", "")
                    length = response.headers.get("Content-Length")
                    if length and int(length) > 200 * 1024 * 1024:
                        raise ValueError("File exceeds the 200 MiB acquisition limit.")
                    received = 0
                    with part.open("wb") as f:
                        while chunk := response.read(1024 * 1024):
                            received += len(chunk)
                            if received > 200 * 1024 * 1024:
                                raise ValueError("File exceeds the 200 MiB acquisition limit.")
                            f.write(chunk)
                    effective_url = response.geturl()
                if not is_expected_file(part, fmt):
                    raise ValueError("Response is not the expected PDF/PPTX (possibly an HTML access page).")
                part.replace(dest)
                event.update(status="DOWNLOADED_VALID_SIGNATURE", url=url, effective_url=effective_url,
                             content_type=content_type, path=str(dest.relative_to(ROOT)),
                             sha256=sha256(dest), size_bytes=dest.stat().st_size)
                return event
            except (OSError, ValueError, urllib.error.URLError) as exc:
                event["errors"].append(f"{url} attempt={attempt+1}: {type(exc).__name__}: {exc}")
                if part.exists():
                    part.unlink()
                # No retry/access-control bypass for denied requests.
                if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 404}:
                    break
                if attempt == 0:
                    time.sleep(2)
    return event


def main():
    p = argparse.ArgumentParser(description="Download source originals on your own computer; record actual byte hashes.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--ids", nargs="+", help="Default: TH-01 VB-X1")
    g.add_argument("--all", action="store_true", help="All registered sources; reserved sources need separate consent")
    p.add_argument("--include-reserved", action="store_true", help="Explicitly include DEV/EVAL_RESERVED originals")
    args = p.parse_args()
    pack = json.loads((ROOT / "sources/source_manifest_v01.json").read_text(encoding="utf-8"))
    by_id = {s["source_id"]: s for s in pack["sources"]}
    ids = list(by_id) if args.all else (args.ids or ["TH-01", "VB-X1"])
    unknown = set(ids) - set(by_id)
    if unknown:
        raise SystemExit("Unknown source IDs: " + ", ".join(sorted(unknown)))
    selected = []
    for sid in ids:
        s = by_id[sid]
        if "RESERVED" in s["planned_split"] and not args.include_reserved:
            print(f"SKIP {sid}: {s['planned_split']} (use --include-reserved for explicit acquisition)")
            continue
        selected.append(s)
    dest_dir = ROOT / "sources/originals"
    dest_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for s in selected:
        print("FETCH", s["source_id"], s["native_format"], flush=True)
        r = acquire(s, dest_dir)
        results.append(r)
        print(" ", r["status"], r.get("path", ""), flush=True)
        if r["status"] == "FAILED":
            print("  Open the source landing page in your browser:", s["landing_url"])
            for e in r["errors"]:
                print(" ", e)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = ROOT / "reports" / f"source_acquisition_{stamp}.json"
    write_json(report, {"results": results, "note": "Signature and hash checks do not independently establish copyright or content accuracy."})
    print("Report:", report)
    raise SystemExit(1 if any(r["status"] == "FAILED" for r in results) else 0)

if __name__ == "__main__":
    main()
