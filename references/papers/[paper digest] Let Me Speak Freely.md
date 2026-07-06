# Let Me Speak Freely

**Title**: Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language Models
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2408.02442
**Publication date**: 2024-08 (first arXiv version)

## Core mechanism + measured results
- Studies how format-restricted / constrained decoding (e.g. forcing JSON or a fixed schema for the answer) affects LLM reasoning quality
- Compares (a) constrained decoding to a strict schema vs (b) free-form generation then a separate parse/convert step
- Constrained/JSON-schema answering costs roughly 10-15% accuracy on reasoning-heavy tasks vs free-form-then-convert
- Tighter the format constraint, the larger the reasoning degradation
- Recommendation: let the model reason in natural language first, then extract structure in a second pass
- Effect observed across multiple models and reasoning benchmarks

## Relevance to Knowledge Graph Foundry
Warns KGF against forcing extraction/answer LLMs directly into rigid JSON graph schemas; prefer free-form reasoning then structured extraction to protect Bayesian entity-resolution and answer quality.
