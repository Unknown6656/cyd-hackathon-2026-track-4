#!/usr/bin/env python3
"""Phase-1 red-team runner for the Track-4 analyst assistant.

Black-box: sends each probe in probes/probes.json to POST <target>/query and
records the full request/response exchange under runs/<runid>/ for evidence.

Usage:
    TARGET_URL=https://host python3 redteam.py
    python3 redteam.py --target https://host --only confidentiality.watchlist
    python3 redteam.py --only inject,detect --delay 0.5 --timeout 180
    python3 redteam.py --list

Notes:
  * queries are serial and throttled (--delay); the target is slow (~25 s/query).
  * everything is logged raw, including non-JSON bodies and HTTP errors, so the
    evidence survives even when the target misbehaves.
"""

import argparse
import csv
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_PROBES = HERE / "probes" / "probes.json"
DEFAULT_OUTDIR = HERE / "runs"

CANARY_RE = re.compile(r"CANARY-[A-Z0-9]+-[0-9]+")


def load_probes(path):
    data = json.loads(pathlib.Path(path).read_text())
    probes = data["probes"] if isinstance(data, dict) else data
    seen = set()
    for p in probes:
        if p["id"] in seen:
            raise SystemExit(f"duplicate probe id: {p['id']}")
        seen.add(p["id"])
        if "payload" not in p:
            raise SystemExit(f"probe {p['id']} has no payload")
    return probes


def select(probes, only):
    if not only:
        return probes
    keys = [k.strip() for k in only.split(",") if k.strip()]
    out = []
    for p in probes:
        if p["id"] in keys or p["category"] in keys:
            out.append(p)
            continue
        if any(p["id"].startswith(k) for k in keys):
            out.append(p)
            continue
        if any(p["category"].startswith(k) for k in keys):
            out.append(p)
    return out


def post_json(url, payload, timeout):
    """POST payload as JSON; always return a dict, never raise."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "cyd-redteam-timoll/1.0"},
        method="POST",
    )
    started = time.time()
    status = None
    headers = {}
    text = ""
    error = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            headers = {k: v for k, v in resp.headers.items()}
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        headers = {k: v for k, v in exc.headers.items()}
        try:
            text = exc.read().decode("utf-8", "replace")
        except Exception:
            text = ""
    except Exception as exc:  # timeout, conn refused, TLS, ...
        error = f"{type(exc).__name__}: {exc}"
    latency = round(time.time() - started, 3)

    parsed = None
    try:
        parsed = json.loads(text)
    except Exception:
        pass

    return {
        "status": status,
        "latency_s": latency,
        "headers": headers,
        "body_text": text,
        "body_json": parsed,
        "error": error,
    }


def summarize(probe, result):
    body = result.get("body_json") if isinstance(result.get("body_json"), dict) else {}
    answer = body.get("answer") if isinstance(body, dict) else None
    answer = answer if isinstance(answer, str) else ""
    canaries = sorted(set(CANARY_RE.findall(answer)) | set(CANARY_RE.findall(result.get("body_text") or "")))
    conf = body.get("confidence")
    ids = body.get("source_post_ids")
    return {
        "id": probe["id"],
        "category": probe["category"],
        "status": result.get("status"),
        "latency_s": result.get("latency_s"),
        "confidence": conf,
        "n_sources": len(ids) if isinstance(ids, list) else "",
        "assessment_score": body.get("assessment_score"),
        "detail_error": body.get("detail") if isinstance(body, dict) else "",
        "canaries": ";".join(canaries),
        "transient_error": result.get("error") or "",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probes", default=str(DEFAULT_PROBES))
    ap.add_argument("--target", default=os.environ.get("TARGET_URL", ""))
    ap.add_argument("--only", default="", help="comma list of ids/prefixes/categories")
    ap.add_argument("--ids-file", default="", help="file with one probe id per line to run")
    ap.add_argument("--timeout", type=float, default=150.0)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between queries")
    ap.add_argument("--retries", type=int, default=4,
                    help="retries on network error / 5xx (the target 504s at ~30s "
                         "on a server-side routing timeout; ~58%% succeed per attempt)")
    ap.add_argument("--retry-backoff", type=float, default=2.0,
                    help="seconds between retries (multiplied by attempt number)")
    ap.add_argument("--max", type=int, default=0, help="cap number of probes (0 = all)")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    ap.add_argument("--list", action="store_true", help="list selected probes and exit")
    args = ap.parse_args()

    probes = select(load_probes(args.probes), args.only)
    if args.ids_file:
        wanted = {
            line.strip()
            for line in pathlib.Path(args.ids_file).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        by_id = {p["id"]: p for p in probes}
        missing = sorted(wanted - by_id.keys())
        if missing:
            raise SystemExit(f"{len(missing)} ids not found in probes file: {missing[:10]}")
        probes = [by_id[i] for i in sorted(wanted)]
    if args.max:
        probes = probes[: args.max]

    if args.list:
        for p in probes:
            print(f"{p['id']:14s} {p['category']:36s} {p['intent']}")
        print(f"\n{len(probes)} probes selected")
        return 0

    if not args.target:
        raise SystemExit("no target: pass --target or set TARGET_URL")
    target = args.target.rstrip("/")
    url = target + "/query"

    runid = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rundir = pathlib.Path(args.outdir) / runid
    rundir.mkdir(parents=True, exist_ok=True)

    (rundir / "manifest.json").write_text(
        json.dumps(
            {
                "runid": runid,
                "target": target,
                "url": url,
                "started_utc": runid,
                "timeout_s": args.timeout,
                "delay_s": args.delay,
                "probes_file": str(pathlib.Path(args.probes).resolve()),
                "n_probes": len(probes),
            },
            indent=2,
        )
        + "\n"
    )

    rows = []
    print(f"[redteam] target={url}  run={rundir}  probes={len(probes)}")
    for i, probe in enumerate(probes, 1):
        attempts = 0
        while True:
            attempts += 1
            result = post_json(url, probe["payload"], args.timeout)
            retryable = result["error"] is not None or (result["status"] or 0) >= 500
            if retryable and attempts <= args.retries:
                print(f"  retry {probe['id']} (attempt {attempts + 1})")
                time.sleep(args.retry_backoff * attempts)
                continue
            break

        record = {
            "probe": probe,
            "request": {"method": "POST", "url": url, "body": probe["payload"]},
            "attempts": attempts,
            "response": result,
        }
        (rundir / f"{probe['id']}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n"
        )
        row = summarize(probe, result)
        rows.append(row)
        canary = f"  CANARY={row['canaries']}" if row["canaries"] else ""
        print(
            f"  [{i:3d}/{len(probes)}] {probe['id']:14s} "
            f"status={row['status']} {row['latency_s']}s conf={row['confidence']} "
            f"src={row['n_sources']}{canary}"
        )
        if i < len(probes) and args.delay:
            time.sleep(args.delay)

    fields = [
        "id", "category", "status", "latency_s", "confidence", "n_sources",
        "assessment_score", "detail_error", "canaries", "transient_error",
    ]
    with (rundir / "summary.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[redteam] wrote {len(rows)} exchanges to {rundir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
