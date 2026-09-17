import importlib
import json
import os
import sys
from typing import Any

import requests

DEFAULT_TEST_MODULE = "run_01_test_cases"
DEFAULT_OUTPUT_DIR = "run_01_test_outputs"
URL = "https://llmhack-team-4.hackathon.intlab.ch/query"


def run_test_case(
    endpoint_url: str,
    test_case: dict[str, Any],
    timeout: int = 30,
) -> dict[str, str | None]:
    use_case_name = test_case.get("use_case_name", "unnamed")
    payload = test_case.get("input")

    entry = {
        "test_case": use_case_name,
        "question": "",
        "answer": None,
    }

    if isinstance(payload, dict):
        entry["question"] = json.dumps(payload)
        entry["answer"] = None
    else:
        entry["question"] = str(payload)

    if payload is None or isinstance(payload, str) or not isinstance(payload, dict):
        print(f"  Question: {entry['question']}")
        print(f"  Response: ERROR - invalid payload")
        print()
        return entry

    try:
        resp = requests.post(
            endpoint_url,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
    except requests.exceptions.ConnectionError:
        print(f"  Question: {entry['question']}")
        print(f"  Response: FAIL - Could not connect to {endpoint_url}")
        print()
        return entry
    except requests.exceptions.Timeout:
        print(f"  Question: {entry['question']}")
        print(f"  Response: FAIL - Timed out after {timeout}s")
        print()
        return entry
    except Exception as e:
        print(f"  Question: {entry['question']}")
        print(f"  Response: ERROR - {e}")
        print()
        return entry

    try:
        body = resp.json()
    except json.JSONDecodeError:
        print(f"  Question: {entry['question']}")
        print(f"  Response: Non-JSON (HTTP {resp.status_code}): {resp.text[:200]}")
        print()
        return entry

    response_text = json.dumps(body, indent=2, ensure_ascii=False)
    print(f"  Question: {entry['question']}")
    print(f"  Response: {response_text}")
    print()

    entry["answer"] = body
    return entry


def run_category(
    endpoint_url: str,
    cat_name: str,
    test_cases: list[dict[str, Any]],
    output_dir: str,
    timeout: int = 30,
) -> None:
    print(f"\n{'=' * 72}")
    print(f"  Category: {cat_name}")
    print(f"{'=' * 72}")

    os.makedirs(output_dir, exist_ok=True)

    results: list[dict[str, str | None]] = []
    for tc in test_cases:
        result = run_test_case(endpoint_url, tc, timeout=timeout)
        results.append(result)

    output_path = os.path.join(output_dir, f"{cat_name}.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(results)} results to {output_path}")


def run_all(
    endpoint_url: str,
    output_dir: str,
    timeout: int = 30,
    categories: list[str] | None = None,
) -> None:
    print(f"{'=' * 72}")
    print(f"{'Track 4 Test Suite':^72}")
    print(f"{'=' * 72}")

    for cat_name, test_cases in ALL_TEST_CASES.items():
        if categories is not None and cat_name not in categories:
            continue
        run_category(endpoint_url, cat_name, test_cases, output_dir, timeout=timeout)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Track 4 test cases against an endpoint")
    parser.add_argument("url", nargs="?", default=URL, help="Endpoint URL")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--category", action="append", help="Run only specific categories (can be repeated)")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory for results JSON files")
    parser.add_argument("--test-module", default=DEFAULT_TEST_MODULE, help="Python module containing ALL_TEST_CASES")
    args = parser.parse_args()

    try:
        mod = importlib.import_module(args.test_module)
    except ImportError:
        mod = importlib.import_module(f"krh.{args.test_module}")

    ALL_TEST_CASES = mod.ALL_TEST_CASES

    run_all(args.url, output_dir=args.output_dir, timeout=args.timeout, categories=args.category)