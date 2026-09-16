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


def send(base: str, payload: dict, tag: str, retries: int = 5, timeout: float = 600) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = RAW / base.rsplit("/", 1)[-1].replace(":", "_").replace(".", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stamp}-{tag}.json"

    record = {"timestamp": stamp, "target": base, "tag": tag, "request": payload}
    for attempt in range(retries):
        started = time.time()
        try:
            resp = requests.post(f"{base}/query", json=payload, timeout=timeout)
            record.update({
                "status": resp.status_code,
                "latency_ms": int((time.time() - started) * 1000),
                "response": resp.json() if "json" in resp.headers.get("content-type", "") else resp.text,
            })
            break
        except Exception as e:
            record.update({
                "error": repr(e),
                "latency_ms": int((time.time() - started) * 1000),
            })
            if attempt < retries - 1:
                backoff = 15 * (attempt + 1)
                print(f"[retry] {tag}: {e!r:.80} — waiting {backoff}s", flush=True)
                time.sleep(backoff)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"=== {tag} -> {out}", flush=True)
    print(json.dumps(record.get("response", record.get("error")), indent=2, ensure_ascii=False)[:4000], flush=True)


def has_success(out_dir: Path, tag: str) -> bool:
    for f in out_dir.glob(f"*-{tag}.json"):
        try:
            if json.loads(f.read_text()).get("status") == 200:
                return True
        except Exception:
            pass
    return False


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    argv = sys.argv[1:]
    tag = None
    if "--tag" in argv:
        i = argv.index("--tag")
        tag = argv[i + 1]
        del argv[i : i + 2]
    argv = [a for a in argv if a != "--batch"]
    target, arg = argv[0], argv[1]
    base = TARGETS.get(target)
    if not base:
        sys.exit(f"target '{target}' not set in scripts/targets.json")
    out_dir = RAW / base.rsplit("/", 1)[-1].replace(":", "_").replace(".", "_")

    if "--batch" in sys.argv:
        items = json.loads(Path(arg).read_text())
        items = items.items() if isinstance(items, dict) else [(f"p{i:02d}", p) for i, p in enumerate(items)]
        for t, p in items:
            t = t or tag or "untagged"
            if has_success(out_dir, t):
                print(f"=== {t} SKIP (already succeeded)", flush=True)
                continue
            send(base, p, t)
    else:
        payload = json.loads(Path(arg).read_text() if arg.endswith(".json") and Path(arg).exists() else arg)
        send(base, payload, tag or "untagged")


if __name__ == "__main__":
    main()
