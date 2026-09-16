#!/usr/bin/env python3
"""Tabulate controlled evasion families from a redteam.py run.

Reads the run's *.json, parses intents of the form "<family> / <style>", and
prints assessment_score per family/style plus the spread within each family.

Usage:
    python3 evasion_report.py runs/20260916T123213Z
    python3 evasion_report.py            # newest run
"""

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_OUTDIR = HERE / "runs"


def latest_rundir(outdir):
    runs = sorted(p for p in pathlib.Path(outdir).iterdir() if p.is_dir())
    if not runs:
        raise SystemExit(f"no run directories under {outdir}")
    return runs[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rundir", nargs="?", default="")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    args = ap.parse_args()
    rundir = pathlib.Path(args.rundir) if args.rundir else latest_rundir(args.outdir)

    import json
    rows = []
    for f in sorted(rundir.glob("*.json")):
        if f.name == "manifest.json":
            continue
        rec = json.loads(f.read_text())
        intent = rec.get("probe", {}).get("intent", "")
        body = rec.get("response", {}).get("body_json") or {}
        score = body.get("assessment_score")
        if score is None:
            continue
        fam, _, style = intent.rpartition(" / ")
        rows.append((fam or "?", style or intent, score, f.name))

    if not rows:
        raise SystemExit(f"no scored assess_post probes in {rundir}")

    by_family = {}
    for fam, style, score, _ in rows:
        by_family.setdefault(fam, []).append((style, score))

    for fam in sorted(by_family):
        items = sorted(by_family[fam], key=lambda t: t[1])
        lo, hi = items[0][1], items[-1][1]
        print(f"\n{fam}  (n={len(items)}, spread {lo:.3f} -> {hi:.3f}, delta {hi - lo:.3f})")
        for style, score in items:
            bar = "#" * max(1, int(round(score * 40)))
            print(f"  {score:.3f}  {bar:<40} {style}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
