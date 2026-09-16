# timoll — Track 4 red team (Phase 1: query attacks)

Black-box red teaming of another team's Twitter-disinformation analyst
assistant through its only public surface, `POST /query`.

Target for this phase: `https://llmhack-team-4.hackathon.intlab.ch/`
(set `TARGET_URL` or pass `--target`; nothing is hard-coded).

Scope: **`POST /query` only**. No corpus injection (Phase 2), no DoS, no
attempt to reach the target's source, prompts, or filesystem.

**Results:** see [`FINDINGS.md`](FINDINGS.md). Headline confirmed exploit —
a watchlist membership oracle via `assess_post.metadata.author` (F-01).

## Files

| Path | Purpose |
|---|---|
| `probes/build_probes.py` | builds the payload library; edit this, not the JSON |
| `probes/probes.json` | generated library, 182 probes across 13 categories |
| `probes/membership.json` | generated per-handle watchlist probes (optional) |
| `redteam.py` | runs probes against `/query`, logs every exchange to `runs/<runid>/` |
| `rerun_failed.py` | collects non-200 probe ids from a run for a retry pass |
| `analyze.py` | mechanical triage of a run into `triage.csv` + candidate findings |
| `evasion_report.py` | tabulates controlled evasion families (F-02) by score spread |
| `gen_membership.py` | emits one membership-inference probe per handle in a list |
| `handles_seed.txt` | known handles to seed the membership sweep |
| `FINDINGS.md` | confirmed/candidate exploits, evidence, reproduction |
| `F-02-report.md` | standalone, code-free write-up of the F-02 evasion exploit (curl reproduction) |
| `runs/` | raw request/response evidence (one JSON per probe + `summary.csv`) |

## Run it

```sh
# regenerate the library after editing build_probes.py
python3 probes/build_probes.py

# see what will run
python3 redteam.py --list
python3 redteam.py --list --only confidentiality.watchlist

# full sweep (slow: the target takes 25-110 s per query)
TARGET_URL=https://llmhack-team-4.hackathon.intlab.ch python3 redteam.py --delay 0.5

# a single category / probe
python3 redteam.py --only inject --delay 0.5
python3 redteam.py --only time-001

# retry only the probes that did not return 200 in the newest run
python3 rerun_failed.py
python3 redteam.py --ids-file runs/<runid>/failed_ids.txt --retries 6

# triage the newest run
python3 analyze.py

# watchlist membership sweep from discovered handles
python3 gen_membership.py handles_seed.txt
python3 redteam.py --probes probes/membership.json --delay 0.5
```

Everything is standard library Python 3 — no dependencies to install.

## Attack categories

1. `confidentiality.watchlist` — direct extraction, membership inference, negative-space, count/confidence side channels.
1b. `confidentiality.watchlist.author-oracle` — `assess_post.metadata.author` as a membership oracle (see `FINDINGS.md` F-01, confirmed).
2. `confidentiality.detection-logic` — feature/threshold extraction, evasion coaching.
2b. `confidentiality.router-bypass` + `integrity.injection-obedience.bypass` — extraction/instructions framed as legitimate in-domain topic/hashtag/account work, to get past the target's intent router. Select both with `--only byp`.
3. `integrity.injection-obedience` — override, roleplay, delimiter break, base64/unicode, injection via `assess_post.content` and `metadata`; each carries a unique `CANARY-INJ-*` token so obedience is mechanically detectable.
4. `integrity.hallucination` — nonexistent authors/hashtags/events, fabricated post IDs.
5. `integrity.overconfidence` — confident claims from zero/one source.
6. `integrity.correctness` — false-positive/false-negative controls via `assess_post`.
6b. `integrity.correctness.evasion-controlled` / `.evasion-families` — fixed claims rephrased across styles to measure score sensitivity (F-02); report with `evasion_report.py`.
7. `integrity.scope-language` — forcing non-English into findings.
8. `discovery.authors` — enumerate candidate handles for membership inference.
9. `robustness.default-time-scope` — suspected hard-coded 2023 window.
10. `robustness.io-contract` — malformed/boundary payloads.

## Notes / gotchas

- **The target 504s at a hard ~30 s server-side timeout.** Successful queries
  take 22-29 s, failures all land at 30.0-30.2 s and return
  `{"detail":"The routing stage timed out. Please try again shortly."}`. Our
  client `--timeout` cannot help; only retrying can. `redteam.py` now defaults to
  4 retries with backoff, and `rerun_failed.py` sweeps whatever is left.
  Observed first-attempt success rate ≈ 58%.
- The target's **intent router is the first defense**: anything not clearly
  about "a topic, hashtag, mention, or an account you specify" gets a canned
  refusal at `confidence: 1.0` with zero sources, before any retrieval. The
  `*router-bypass` probes exist to test that gate.
- The target is **slow and non-deterministic**: the same query returned
  `confidence=1.0, 0 sources, "scope 2023"` on one run and
  `confidence=0.5, 13 sources` on another. Always reproduce a finding 3x before
  claiming it.
- `analyze.py` is heuristic; a hit is a lead, not proof. Read the raw JSON in
  `runs/` and confirm by hand.
- Probe files are plain JSON: `{id, category, intent, payload}`, `payload` is the
  exact request body.
