"""Thin client for the blue team's POST /query endpoint.

The request contract (from the task spec):
    request:  { "query": <str>, "assess_post": { "content": <str>,
                                                 "metadata": { "author", "timestamp", "language" } }? }
    response: { "answer": <str>, "source_post_ids": [str],
                "source_post_content": {...}?, "confidence": float,
                "assessment_score": float }   # assessment_score only when assess_post sent

We are a black box: we only ever see this I/O. No source, no prompts, no corpus.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_target(cli: Optional[str]) -> str:
    """Resolve the target base URL from CLI arg > $RT_TARGET > config.env.

    Accepts "host:port", "https://host:port", or "https://host:port/".
    """
    t = cli or os.environ.get("RT_TARGET") or _read_config_target() or ""
    t = t.strip().strip('"').strip("'").rstrip("/")
    if not t:
        return ""
    if not t.startswith("http://") and not t.startswith("https://"):
        t = "https://" + t
    return t


def _read_config_target() -> Optional[str]:
    """Read RT_TARGET from ./config.env if present (one KEY=VALUE per line)."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(here, "config.env")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("RT_TARGET="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


@dataclass
class RTResponse:
    """One request/response pair plus transport metadata. JSON-serialisable."""

    attack_id: str
    attack_class: str
    request: dict
    status_code: Optional[int] = None
    latency_ms: int = 0
    parsed: Optional[dict] = None
    raw_text: Optional[str] = None
    error: Optional[str] = None
    ts: str = field(default_factory=utcnow)

    @property
    def ok(self) -> bool:
        """Transport-level success: HTTP 200 with a JSON object body."""
        return self.status_code == 200 and isinstance(self.parsed, dict)

    def answer_text(self) -> str:
        if self.parsed and isinstance(self.parsed.get("answer"), str):
            return self.parsed["answer"]
        return ""

    def confidence(self) -> Optional[float]:
        if self.parsed and isinstance(self.parsed.get("confidence"), (int, float)):
            return float(self.parsed["confidence"])
        return None

    def assessment_score(self) -> Optional[float]:
        if self.parsed and isinstance(self.parsed.get("assessment_score"), (int, float)):
            return float(self.parsed["assessment_score"])
        return None

    def source_post_ids(self) -> list:
        if self.parsed and isinstance(self.parsed.get("source_post_ids"), list):
            return self.parsed["source_post_ids"]
        return []

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


class Client:
    def __init__(self, target: str, timeout: int = 90, verify: bool = True):
        if not target:
            raise ValueError(
                "No target URL. Pass --target, set RT_TARGET, or create config.env "
                "(see config.example.env)."
            )
        self.url = target.rstrip("/") + "/query"
        self.timeout = timeout
        self.verify = verify

    def _post(self, payload: dict) -> RTResponse:
        t0 = time.time()
        try:
            r = requests.post(
                self.url, json=payload, timeout=self.timeout, verify=self.verify
            )
            lat = int((time.time() - t0) * 1000)
            try:
                parsed: Optional[dict] = r.json()
            except ValueError:
                parsed = None
            return RTResponse(
                attack_id="", attack_class="",
                request=payload,
                status_code=r.status_code, latency_ms=lat,
                parsed=parsed if isinstance(parsed, dict) else None,
                raw_text=r.text, error=None,
            )
        except requests.exceptions.RequestException as exc:  # network / timeout
            lat = int((time.time() - t0) * 1000)
            return RTResponse(
                attack_id="", attack_class="",
                request=payload,
                status_code=None, latency_ms=lat,
                parsed=None, raw_text=None, error=str(exc),
            )

    def query(self, attack_id: str, attack_class: str, query: str) -> RTResponse:
        resp = self._post({"query": query})
        resp.attack_id, resp.attack_class = attack_id, attack_class
        return resp

    def assess(self, attack_id: str, attack_class: str, content: str,
               author: Optional[str] = None, timestamp: Optional[str] = None,
               language: Optional[str] = None,
               query: Optional[str] = None) -> RTResponse:
        """Send a post for assessment. `query` may steer how the post is framed."""
        assess_post = {"content": content}
        meta = {}
        if author is not None:
            meta["author"] = author
        if timestamp is not None:
            meta["timestamp"] = timestamp
        if language is not None:
            meta["language"] = language
        if meta:
            assess_post["metadata"] = meta
        payload = {"assess_post": assess_post}
        if query is not None:
            payload["query"] = query
        resp = self._post(payload)
        resp.attack_id, resp.attack_class = attack_id, attack_class
        return resp

    def query_assess(self, attack_id: str, attack_class: str, query: str,
                     content: str, author: Optional[str] = None,
                     timestamp: Optional[str] = None,
                     language: Optional[str] = None) -> RTResponse:
        """Send both a query and a post to assess in a single request."""
        assess_post = {"content": content}
        meta = {}
        if author is not None:
            meta["author"] = author
        if timestamp is not None:
            meta["timestamp"] = timestamp
        if language is not None:
            meta["language"] = language
        if meta:
            assess_post["metadata"] = meta
        payload = {"query": query, "assess_post": assess_post}
        resp = self._post(payload)
        resp.attack_id, resp.attack_class = attack_id, attack_class
        return resp
