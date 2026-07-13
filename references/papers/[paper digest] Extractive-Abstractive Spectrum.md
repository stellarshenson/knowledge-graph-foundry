# The Extractive-Abstractive Spectrum: Uncovering Verifiability Trade-offs in LLM Generations

**Authors**: Theodora Worledge, Tatsunori Hashimoto, Carlos Guestrin (Stanford University)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2411.17375

**Publication date**: 2024-11-27

## Summary

- Moving from extractive to abstractive cited generation raises perceived utility by **over 200%** but drops citation coverage by **over 50%** and makes sentences take **up to 3x longer** to verify (human eval, 480 queries, 7 systems, 4 query distributions, 31 MTurk annotators)
- Defines five operating points (OPs) on the spectrum: **extractive** (raw source snippets), **quoted** (inline word-for-word quotes, citations inherent), **paraphrased** (reworded but no information added/removed), **entailed** (may remove/compress but adds no new claims), **abstractive** (may contain uncited claims)
- Citation precision holds at **95-100%** across the five reference OPs (all built "attribute first, then generate") but falls sharply for post-hoc citation systems: **43.4%** coverage for GPT-4 + Google Vertex grounding, and only **15.0%** coverage for the deployed Google Gemini "Double-check response" feature, despite Gemini matching entailed-OP fluency and utility
- Citations per cited sentence rise with abstraction: quoted 1.19, paraphrased 1.33, entailed 1.90, abstractive 1.75, GPT-4+Vertex 3.14 - except Gemini, which caps at 1.00 citation per sentence yet still shows high time-to-verify
- Quoted generations keep **82%** of words as direct quotes (avg **14.5 words** per quote); simply rewording quoted into paraphrased generations increases verification time by **over 40%**
- Paraphrasing and entailment fix most quoted-OP quality failures: paraphrased resolves **91.4%** of fluency failures and **65.4%** of utility failures; entailed resolves **98.5%** and **89.6%** respectively
- No single OP is Pareto-optimal - recommends extractive/quoted for high-stakes settings with dispersed, already well-formed information (legal, clinical case lookup), abstractive for low-stakes creative/brainstorming tasks, and paraphrased/entailed as the (imperfect) compromise where high-stakes tasks also need style transformation (patient-facing medical/legal simplification)

**Key mechanism**
- Reference OPs are generated "attribute first, then generate": source quotes are selected before generation, and paraphrased/entailed/abstractive outputs are each a revision of the quoted generation with per-sentence citations re-identified against the original quoted set - this ordering is what keeps precision at 95-100% versus the post-hoc citation pipelines (GPT-4+Vertex, Gemini) that retrieve/attribute citations after the answer is already written
- Verifiability is operationalized as three measurable axes - citation precision (does the cited source support the claim), citation coverage (do citations support ALL claims in the sentence), and time-to-verify (human wall-clock cost) - rather than a single grounding score

**Relevance to Knowledge Graph Foundry**: KGF's retrieval-first doctrine (perfect context in 1-2 hops, minimal query-time traversal) sits squarely on the abstractive end of this spectrum once a synthesized answer is generated from PPR-seeded graph context; this paper's core finding - that post-hoc citation attribution (closer to how a Neo4j-retrieved-then-answered pipeline would work) collapses coverage to 15-43% versus 95-100% for attribute-first designs - argues for pinning entity/passage provenance at extraction/ingest time (already KGF's speculative-ingest-context direction) rather than back-attributing citations after generation, and for treating H382's context-escalation gate as a coverage/verifiability lever, not just a token-budget one.

**Tags**: #Verifiability #CitationQuality #ExtractiveAbstractive #HumanEvaluation #GroundedGeneration
