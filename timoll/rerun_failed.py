#!/usr/bin/env python3
"""Collect probe ids that did not return HTTP 200 in a run, for a retry pass.

The target 504s at ~30 s on a server-side routing timeout (successful queries
take 22-29 s), so a meaningful fraction of probes fail and must be retried.

Usage:
    python3 rerun_failed.py                       # newest run
    python3 rerun_failed.py runs/20260916T113104Z
    # then, with aggressive retries:
    python3 redteam.py --ids-file runs/<runid>/failed_ids.txt --retries 6
"""

import argparse
import csv
import pathlib
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
    summary = rundir / "summary.csv"
    if not summary.exists():
        raise SystemExit(f"no summary.csv in {rundir} (run still in progress?)")

    failed, total = [], 0
    with summary.open() as fh:
        for row in csv.DictReader(fh):
            total += 1
            status = row.get("status") or ""
            if status != "200" or row.get("transient_error"):
                failed.append(row["id"])

    out = rundir / "failed_ids.txt"
    out.write_text("\n".join(failed) + ("\n" if failed else ""))
    print(f"[rerun] {len(failed)}/{total} probes did not return 200 -> {out}")
    if failed:
        print(f"[rerun] retry with: python3 redteam.py --ids-file {out} --retries 6")
    return 0


if __name__ == "__main__":
    sys.exit(main())
