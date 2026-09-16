#!/usr/bin/env python3
"""Build the watchlist-sweep candidate pool from the public fivethirtyeight
IRA dump (cache/ira/IRAhandle_tweets_*.csv).

A handle is a candidate if it plausibly has English-language presence in the
public dump (the target corpus is a subset of it, and the watchlist is a
subset of the target's ENGLISH authors). We err toward a superset:
  - any row with language == 'English', OR
  - primary (most-frequent) account_category != 'NonEnglish'

Output:
  cache/cand-pool.tsv        handle \t primary_category \t n_rows \t n_english
  cache/cand-pool-priority.txt  ordered probe list (influence categories first)
"""
import csv
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = None
author_rows = Counter()
author_lang = defaultdict(Counter)
author_cat = defaultdict(Counter)

for f in sorted(glob.glob(str(ROOT / "cache" / "ira" / "IRAhandle_tweets_*.csv"))):
    with open(f, newline="", encoding="utf-8", errors="replace") as fh:
        r = csv.DictReader(fh)
        for row in r:
            a = row.get("author") or ""
            if not a:
                continue
            a = a.strip()
            author_rows[a] += 1
            author_lang[a][row.get("language") or ""] += 1
            author_cat[a][row.get("account_category") or ""] += 1

def primary(c: Counter) -> str:
    return c.most_common(1)[0][0] if c else ""

cands = {}
for a in author_rows:
    pcat = primary(author_cat[a])
    n_en = author_lang[a].get("English", 0)
    if n_en > 0 or pcat != "NonEnglish":
        cands[a] = (pcat, author_rows[a], n_en)

PRIORITY = ["LeftTroll", "RightTroll", "Fearmonger", "HashtagGamer", "Unknown",
            "NewsFeed", "Commercial", ""]
order = {c: i for i, c in enumerate(PRIORITY)}
ranked = sorted(cands, key=lambda a: (order.get(cands[a][0], 50), -cands[a][1]))

with open(ROOT / "cache" / "cand-pool.tsv", "w") as out:
    out.write("author\tprimary_category\tn_rows\tn_english\n")
    for a in ranked:
        p, n, ne = cands[a]
        out.write(f"{a}\t{p}\t{n}\t{ne}\n")

with open(ROOT / "cache" / "cand-pool-priority.txt", "w") as out:
    for a in ranked:
        out.write(a + "\n")
(ROOT / "payloads" / "sweep-cand-pool.txt").write_text("".join(a + "\n" for a in ranked))

cats = Counter(p for p, _, _ in cands.values())
print(f"unique authors total: {len(author_rows)}")
print(f"candidates: {len(cands)}  (public rows: {sum(author_rows.values())})")
print("candidate category split:", dict(cats))
