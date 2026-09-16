"""valardomate red-team toolkit for Track 4 (Twitter Disinformation Analyst Assistant).

Black-box attacks against a blue team's running assistant, through POST /query only.

Modules:
    client   -- thin HTTP client for the /query endpoint
    battery  -- data-driven registry of every attack payload + rationale
    oracles  -- response heuristics that flag a probable exploit (triage, not proof)

Top-level scripts:
    run.py           -- run the attack battery against a target, dump evidence
    sweep_author.py  -- Phase 1: reconstruct the watchlist via the assess_post membership oracle
    ablation.py      -- Phase 1: reconstruct the detection logic via controlled ablation
    evasion.py       -- Phase 1: iteratively mutate a post to flip its score (evasion demo)

Everything writes JSONL evidence to ./evidence so every claim is reproducible.
"""
