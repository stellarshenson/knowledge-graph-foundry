# api.md Audit Findings - parked 2026-07-10

Code-grounded staleness audit of `docs/api.md` (opus fleet, workflow wf_c04f87d4-168).
Apply these when the user calls for the api.md update. Verify line numbers still hold at apply time.

## Stale

- **Settings sub-model list incomplete** - doc line 52 enumerates 9 sub-models but omits `embedding_channels: EmbeddingChannels` (settings.py:197) and `ingest: IngestSettings` (settings.py:198); note EmbeddingChannels/ChannelEmbedding/IngestSettings are not in `__init__.py` `__all__` - reachable via config.yml / Settings fields, not top-level import

## Missing

- **Foundry methods** - `repair(question, sources)` (pipeline.py:609, re-extracts named source docs with the question as focus, loads into STABLE graph) and `repurpose(purpose, seed=None)` (pipeline.py:201, changes use case in place with purpose_history, requires STABLE) absent from the Entrypoint list
- **Drift knobs** - `cusum_enabled` (False), `cusum_k` (0.02), `cusum_h` (0.30), `recure_adopt_share` (0.05) - settings.py:134-137
- **GraphRAG knobs** - `escalation_gate`, `escalation_threshold_prior` (0.765), `escalation_min_labels` (12), `gate_calibration_path`, `passages_enabled`, `passage_index_name`, `passage_span_chars` (900), `passage_top_k` (settings.py:149-158), plus `miss_detector` (True, :147), `abstention_enabled` (True, :171); also `ppr_enabled` is headlined in the doc but defaults False (H37-refuted, ablation-only, :163)
- **Embeddings channels** - `embedding_channels` -> `EmbeddingChannels.passages` -> `ChannelEmbedding` (provider bedrock|local-gpu|openai, default local-gpu bge-m3, device pinning, endpoint) - settings.py:43-62, extraction/embeddings.py
- **Resolution levers** - `soft_links` (True, :105), `demotion_court` (True, :106), `spec_hoist` (False, :107 - R33-H365 series bridge + spec hoist, graph/hoist.py); optionally `identity_stack`/`nli_veto_threshold`

DESIGN.md findings discarded (file archived 2026-07-10). usage-scenarios.md findings applied same day. gap-ledger.md audited current.
