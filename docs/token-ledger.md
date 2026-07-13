# Local-LLM Token Ledger

Running tally of tokens served by the local gpt-oss-120b (vLLM, own GPU) that would otherwise bill against Bedrock - the equipment's savings, stated internally. Maintained by `scripts/token_ledger.py` at scale boundaries and milestones; raw snapshots in `reports/experiments/token-ledger.jsonl` (instance-aware - counters reset on server restart and are banked per instance).

- **Cumulative** - 20.9M prompt + 33.3M generation = **54.2M tokens** (incl. 19.1M conservative pre-ledger backfill)
- **Saved vs Claude Sonnet 4.5 on Bedrock** (\$3/M in, \$15/M out - KGF's default frontier config): **\$562**
- **Saved vs Claude Haiku 4.5** (\$1/M in, \$5/M out): \$187
- **Marginal local cost** - GPU power only, single-digit dollars

| when (UTC) | instance tokens (P/G) | cumulative | Sonnet-equiv | note |
|---|---|---|---|---|
| 2026-07-11 15:42 | 10.8M / 18.0M | 47.9M | $504 | first snapshot: R30 calibration + H385 replay + 2wiki pilot + medium ingest start (instance since 04:10) |
| 2026-07-11 19:38 | 11.8M / 19.4M | 50.3M | $528 | adversarial review closed; medium ingest mid-flight |
| 2026-07-12 06:38 | 12.6M / 20.4M | 52.1M | $546 | medium boundary closed: dump + H389 certificates x2 (64.1/62.1%) |
| 2026-07-12 09:52 | 0.0M / 0.0M | 52.1M | $546 | post-crash vLLM restart (machine failure ~08:25Z) - new instance baseline |
| 2026-07-12 11:18 | 1.2M / 0.9M | 54.2M | $562 | midday snapshot: R35/R36/H352 executors + Phase-3 rebuild run 1 in flight |
