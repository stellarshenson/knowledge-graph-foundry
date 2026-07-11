# ODKE+: Ontology-Guided Open-Domain Knowledge Extraction with LLMs

**Authors**: Samira Khorshidi, Azadeh Nikfarjam, Suprita Shankar, Yisi Sang, Yash Govind, Hyun Jang, et al. (Apple)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2509.04696

**Publication date**: 2025-09-04 (first arXiv version)

## Summary

- Production-grade pipeline that ingested **19 million facts at 98.8% precision** from **9+ million Wikipedia pages** across **195 predicates** - the largest published LLM-extraction deployment with verification
- Five-stage architecture: **Extraction Initiator** (detects missing or stale facts - extraction is TARGETED at known gaps, not blanket re-extraction), **Evidence Retriever** (collects supporting documents), hybrid **Knowledge Extractors** (pattern rules + ontology-guided LLM prompting), **Grounder** (a second LLM validates each extracted fact against the retrieved evidence), **Corroborator** (ranks and normalizes candidates before ingestion)
- Dynamic ontology snippets: per-entity-type schema fragments are generated and injected into the extraction prompt - type-consistent extraction without shipping the whole ontology per call (the industrial midpoint between constrained and open extraction)
- Coverage outcome: up to **48% overlap with third-party KGs** and **update lag reduced by 50 days** on average - gap-driven extraction demonstrably improves freshness and completeness
- Two operating modes (batch + streaming); precision is bought with a two-LLM chain (extractor then grounder), i.e., verification cost ~doubles extraction cost

**Relevance to Knowledge Graph Foundry**: The only published system whose ENTRY POINT is a completeness signal - "what is missing" drives what gets extracted, which is KGF's gap-ledger doctrine running in production at Apple scale. Its grounder stage is per-fact source verification (trustworthiness) and its initiator is coverage-driven repair; KGF has neither wired, though the self-auditing-foundry doctrine specifies both. Also validates per-type ontology snippets as the prompt-side form of KGF's cured typed ontology.
