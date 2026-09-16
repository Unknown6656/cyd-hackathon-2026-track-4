#!/usr/bin/env python3
"""Black-box probe for a track-4 assistant. Logs every request/response
verbatim into findings/raw/<target>/ for use as exploit evidence.

Usage:
  probe.py <target> '{"query": "..."}'                      # single inline payload
  probe.py <target> --file payloads/x.json                   # single payload from file
  probe.py <target> --batch payloads/batch.json              # {"tag": payload, ...} or [payloads]
  probe.py <target> '{"query": "..."}' --tag a1-direct       # name the evidence file

Requires: requests  (pip install requests)
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TARGETS = json.loads((HERE / "targets.json").read_text())["targets"]
RAW = ROOT / "findings" / "raw"


def send(base: str, payload: dict, tag: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = RAW / base.rsplit("/", 1)[-1].replace(":", "_").replace(".", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stamp}-{tag}.json"

    started = time.time()
    try:
        resp = requests.post(f"{base}/query", json=payload, timeout=300)
        record = {
            "timestamp": stamp,
            "target": base,
            "tag": tag,
            "request": payload,
            "status": resp.status_code,
            "latency_ms": int((time.time() - started) * 1000),
            "response": resp.json() if "json" in resp.headers.get("content-type", "") else resp.text,
        }
    except Exception as e:  # network error is also evidence
        record = {
            "timestamp": stamp,
            "target": base,
            "tag": tag,
            "request": payload,
            "error": repr(e),
            "latency_ms": int((time.time() - started) * 1000),
        }
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"=== {tag} -> {out}")
    print(json.dumps(record.get("response", record.get("error")), indent=2, ensure_ascii=False)[:4000])


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if "--tag" in sys.argv:
        i = sys.argv.index("--tag")
        tag = sys.argv[i + 1]
        rest = [a for j, a in enumerate(sys.argv[1:]) if not (j == i - 1 or j == i)]
    else:
        tag = None
        rest = sys.argv[1:]
    target, arg = rest[0], rest[1]
    base = TARGETS.get(target)
    if not base:
        sys.exit(f"target '{target}' not set in scripts/targets.json")

    if "--batch" in sys.argv:
        items = json.loads(Path(arg).read_text())
        items = items.items() if isinstance(items, dict) else [(f"p{i:02d}", p) for i, p in enumerate(items)]
        for t, p in items:
            send(base, p, t or tag or "untagged")
    else:
        payload = json.loads(Path(arg).read_text() if arg.endswith(".json") and Path(arg).exists() else arg)
        send(base, payload, tag or "untagged")


if __name__ == "__main__":
    main()
