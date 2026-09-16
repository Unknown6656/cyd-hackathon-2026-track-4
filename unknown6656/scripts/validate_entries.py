#!/usr/bin/env python3
"""Validate corpus-injection entries against the exact schema of the two
example posts in _task/data.md. Exit 0 = ready to submit."""
import json
import sys
from pathlib import Path

REQUIRED = {
    "post_id": str, "source_tweet_id": int, "external_author_id": int,
    "author": str, "content": str, "region": str, "language": str,
    "publish_date": str, "harvested_date": str, "following": int,
    "followers": int, "updates": int, "post_type": str, "account_type": str,
    "account_category": str, "retweet": int, "new_june_2018": int,
    "alt_external_id": int, "tweet_id": int, "article_url": str,
    "tco1_step1": (type(None), str), "tco2_step1": (type(None), str),
    "tco3_step1": (type(None), str),
}

def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus-injection/entries.json")
    data = json.loads(path.read_text())
    assert isinstance(data, list), "top level must be a JSON array"
    seen_ids = set()
    for i, e in enumerate(data):
        for field, typ in REQUIRED.items():
            assert field in e, f"[{i}] missing field: {field}"
            assert isinstance(e[field], typ), f"[{i}] {field} wrong type: {type(e[field]).__name__} (want {typ})"
        extra = set(e) - set(REQUIRED)
        assert not extra, f"[{i}] extra fields: {extra}"
        assert e["post_id"] not in seen_ids, f"[{i}] duplicate post_id {e['post_id']}"
        seen_ids.add(e["post_id"])
    print(f"OK: {len(data)} entries valid")

if __name__ == "__main__":
    main()
