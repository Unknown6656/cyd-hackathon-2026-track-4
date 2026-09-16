#!/usr/bin/env python3
"""Run the Track-4 red-team attack battery against a target /query endpoint.

Examples:
    # point at a target and run everything
    python3 run.py --target https://track4.hackathon.intlab.ch:8443

    # or put it in config.env (see config.example.env) and just:
    python3 run.py

    # run only some exploit classes
    python3 run.py --class watchlist,detection_logic

    # run specific attacks by id
    python3 run.py --ids wl-01,hal-01,ai-03

    # dry run: print the payloads without sending anything
    python3 run.py --list
    python3 run.py --dry-run

Every request/response + triage signal is appended to evidence/runs/<ts>.jsonl,
and confirmed/suspected exploits are mirrored to evidence/hits.jsonl so the
write-up has a ready-made, reproducible evidence trail.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from datetime import datetime, timezone

from rt.client import Client, normalize_target
from rt.battery import BATTERY
from rt.oracles import ORACLES, Signal

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE = os.path.join(HERE, "evidence")


def materialize(a, seed: str | None):
    """Return a copy of the attack with SEED_HANDLE substituted if provided."""
    b = copy.copy(a)
    if seed and seed != "SEED_HANDLE":
        if b.query:
            b.query = b.query.replace("SEED_HANDLE", seed)
        if b.assess_author == "SEED_HANDLE":
            b.assess_author = seed
        meta = dict(b.assess_meta)
        if "author" in meta and meta["author"] == "SEED_HANDLE":
            meta["author"] = seed
        b.assess_meta = meta
    return b


def send(client: Client, a) -> "rt.client.RTResponse":
    if a.kind == "query":
        return client.query(a.id, a.cls, a.query or "")
    if a.kind == "assess":
        return client.assess(
            a.id, a.cls, a.assess_content or "",
            author=a.assess_author,
            timestamp=a.assess_meta.get("timestamp"),
            language=a.assess_meta.get("language"),
            query=a.query,
        )
    if a.kind == "both":
        return client.query_assess(
            a.id, a.cls, a.query or "", a.assess_content or "",
            author=a.assess_author,
            timestamp=a.assess_meta.get("timestamp"),
            language=a.assess_meta.get("language"),
        )
    raise ValueError(f"unknown kind {a.kind!r}")


def triage(a, resp) -> Signal:
    name, kwargs = a.oracle if isinstance(a.oracle, tuple) else ("none", {})
    func = ORACLES.get(name)
    if func is None:
        return Signal("none", f"no oracle for {name!r}")
    try:
        return func(resp, **kwargs)
    except TypeError:
        # fall back to no-arg call for oracles with fixed signatures
        return func(resp)


def payload_for(a) -> dict:
    if a.kind == "query":
        return {"query": a.query or ""}
    assess = {"content": a.assess_content or ""}
    meta = {k: v for k, v in (
        {"author": a.assess_author,
         "timestamp": a.assess_meta.get("timestamp"),
         "language": a.assess_meta.get("language")}
    ).items() if v is not None}
    if meta:
        assess["metadata"] = meta
    out = {"assess_post": assess}
    if a.query is not None:
        out["query"] = a.query
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Track-4 red-team attack battery")
    ap.add_argument("--target", help="target base URL (host:port or full URL)")
    ap.add_argument("--class", dest="classes", help="comma list of classes to run")
    ap.add_argument("--ids", help="comma list of attack ids to run")
    ap.add_argument("--list", action="store_true", help="list attacks and exit")
    ap.add_argument("--dry-run", action="store_true", help="print payloads, send nothing")
    ap.add_argument("--seed-handle", help="handle to substitute for SEED_HANDLE")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds to sleep between requests (be polite / avoid rate limits)")
    ap.add_argument("--evidence", default=EVIDENCE, help="evidence output dir")
    args = ap.parse_args()

    # ---- select attacks -------------------------------------------------
    attacks = list(BATTERY)
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        attacks = [a for a in attacks if a.id in wanted]
    if args.classes:
        wanted_cls = {x.strip() for x in args.classes.split(",") if x.strip()}
        attacks = [a for a in attacks if a.cls in wanted_cls]

    if args.list:
        print(f"{'id':8} {'class':18} {'kind':6}  rationale")
        for a in attacks:
            print(f"{a.id:8} {a.cls:18} {a.kind:6}  {a.rationale}")
        print(f"\n{len(attacks)} attack(s).")
        return 0

    seed = args.seed_handle
    if args.dry_run:
        for a in attacks:
            a = materialize(a, seed)
            print(f"\n== {a.id} [{a.cls}] kind={a.kind} ==")
            print(json.dumps(payload_for(a), ensure_ascii=False, indent=2))
        print(f"\n[dry-run] {len(attacks)} payload(s) would be sent.")
        return 0

    target = normalize_target(args.target)
    if not target:
        print("error: no target. Use --target, RT_TARGET, or config.env.", file=sys.stderr)
        return 2
    client = Client(target, timeout=args.timeout, verify=not args.insecure)

    os.makedirs(os.path.join(args.evidence, "runs"), exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_path = os.path.join(args.evidence, "runs", f"run_{stamp}.jsonl")
    hits_path = os.path.join(args.evidence, "hits.jsonl")

    print(f"target: {target}")
    print(f"evidence: {run_path}")
    print("-" * 78)

    counts = {"strong": 0, "suspect": 0, "none": 0, "error": 0}
    strong_hits = []
    with open(run_path, "a", encoding="utf-8") as rf, \
         open(hits_path, "a", encoding="utf-8") as hf:
        for a in attacks:
            a = materialize(a, seed)
            resp = send(client, a)
            sig = triage(a, resp)
            record = json.loads(resp.to_json())
            record["signal"] = {"level": sig.level, "note": sig.note}
            rf.write(json.dumps(record, ensure_ascii=False) + "\n")
            rf.flush()

            mark = {"strong": "🔴 STRONG", "suspect": "🟡 suspect",
                    "none": "·    none", "error": "⚫ error"}[sig.level]
            counts[sig.level] = counts.get(sig.level, 0) + 1
            if resp.error:
                counts["error"] += 1
            short = sig.note if len(sig.note) < 55 else sig.note[:52] + "..."
            print(f"{a.id:8} {a.cls:18} {mark:11} {short}")

            if sig.level in ("strong", "suspect"):
                hit = {
                    "ts": resp.ts, "attack_id": a.id, "class": a.cls,
                    "level": sig.level, "signal_note": sig.note,
                    "rationale": a.rationale, "success_criterion": a.success,
                    "target": target,
                    "request": resp.request,
                    "response": resp.parsed if resp.ok else resp.raw_text,
                    "status_code": resp.status_code,
                }
                hf.write(json.dumps(hit, ensure_ascii=False) + "\n")
                hf.flush()
                if sig.level == "strong":
                    strong_hits.append(a.id)

            if args.sleep:
                time.sleep(args.sleep)

    print("-" * 78)
    print(f"total {len(attacks)} | strong {counts['strong']} | "
          f"suspect {counts['suspect']} | none {counts['none']} | "
          f"errors {counts['error']}")
    if strong_hits:
        print(f"\n🔴 STRONG hits to review: {', '.join(strong_hits)}")
    print(f"\nReview: {hits_path}\nFull log: {run_path}")
    print("Auto-flags are triage — read each `response.answer` before claiming a win.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
