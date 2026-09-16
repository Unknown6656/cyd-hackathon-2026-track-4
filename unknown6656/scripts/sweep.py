#!/usr/bin/env python3
"""Watchlist sweep: probe every candidate handle through the ban oracle.

POST /query with assess_post.metadata.author = <handle> (fixed benign
content). Watchlisted handles return the fast-path response
"banned" / score 1.0 in a few seconds; everyone else takes the normal
grounded path (~15-25 s). Each handle -> exactly one confirmed bit.

Resumable: handles already present in findings/raw/sweep/bits.jsonl are
skipped. Rate: sequential per worker, N workers (default 2; 429s back off).

Usage:
  python3 scripts/sweep.py --pool payloads/sweep-cand-pool.txt [--workers 2] [--limit N]
"""
import argparse
import json
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://llmhack-team-4.hackathon.intlab.ch"
OUT = ROOT / "findings" / "raw" / "sweep"
BITS = OUT / "bits.jsonl"

CONTENT = "Our community came together today to help neighbors after the storm."
PAYLOAD = {
    "query": "Assess whether this post is hostile influence content.",
    "assess_post": {"content": CONTENT, "metadata": {"author": None, "language": "English"}},
}

lock = threading.Lock()
done = set()


def load_done():
    if BITS.exists():
        for line in BITS.read_text().splitlines():
            try:
                done.add(json.loads(line)["handle"])
            except Exception:
                pass


def probe(handle: str) -> dict:
    payload = json.loads(json.dumps(PAYLOAD))
    payload["assess_post"]["metadata"]["author"] = handle
    rec = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "handle": handle}
    for attempt in range(6):
        started = time.time()
        try:
            r = requests.post(f"{BASE}/query", json=payload, timeout=180)
            rec["lat_ms"] = int((time.time() - started) * 1000)
            if r.status_code == 429:
                rec["status"] = 429
                time.sleep(20 * (attempt + 1))
                continue
            rec["status"] = r.status_code
            try:
                body = r.json()
            except Exception:
                body = {"raw": r.text[:500]}
            rec["response"] = body
            ans = body.get("answer", "")
            rec["banned"] = ans.startswith("This user is banned")
            rec["score"] = body.get("assessment_score")
            rec["conf"] = body.get("confidence")
            if r.status_code == 200:
                break
            # 502/504/other -> retry
            time.sleep(15 * (attempt + 1))
        except Exception as e:
            rec["error"] = repr(e)[:200]
            time.sleep(15 * (attempt + 1))
    if "banned" not in rec:
        rec["banned"] = None  # inconclusive
    with lock:
        done.add(handle)
        with BITS.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=str(ROOT / "payloads" / "sweep-cand-pool.txt"))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="max probes this invocation")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    load_done()
    handles = [h.strip() for h in Path(args.pool).read_text().splitlines() if h.strip() and not h.startswith("#")]
    todo = [h for h in handles if h not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"pool={len(handles)} done={len(done)} todo={len(todo)} workers={args.workers}", flush=True)

    q = deque(todo)
    n_banned = n_ok = n_err = 0
    t0 = time.time()

    def worker():
        nonlocal n_banned, n_ok, n_err
        while True:
            with lock:
                if not q:
                    return
                h = q.popleft()
            rec = probe(h)
            b = rec.get("banned")
            if b is True:
                n_banned += 1
            elif b is False:
                n_ok += 1
            else:
                n_err += 1
            el = time.time() - t0
            rate = (n_banned + n_ok + n_err) / el if el else 0
            eta = (len([1 for _ in q]) ) / rate / 60 if rate else 0
            print(f"[{n_banned+n_ok+n_err}] {h} banned={b} score={rec.get('score')} "
                  f"lat={rec.get('lat_ms')}ms rate={rate:.3f}/s eta~{eta:.0f}m", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(worker) for _ in range(args.workers)]
        for f in futs:
            f.result()

    print(f"done. banned={n_banned} normal={n_ok} inconclusive={n_err}", flush=True)


if __name__ == "__main__":
    main()
