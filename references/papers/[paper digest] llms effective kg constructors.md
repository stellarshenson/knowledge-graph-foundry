# Are Large Language Models Effective Knowledge Graph Constructors?

**arXiv 2510.11297 (2025), Chen et al.** Proposes a **hierarchical extraction framework** that builds knowledge graphs at multiple levels of granularity rather than a single flat entity/relation pass, and evaluates state-of-the-art LLMs on the resulting graphs from both structural and semantic angles. Releases a curated dataset of LLM-generated KGs from children's mental-well-being research papers as a benchmarking resource for high-stakes domains.

**Key mechanism**: extraction is organized hierarchically - information is captured at multiple structural levels (beyond sentence-level entity/relation triples) instead of relying on a single predefined schema, aiming to preserve semantically rich, well-structured output that a flat single-pass extraction would lose.

**Main findings**: existing LLM-based KG construction approaches over-focus on narrow entity/relation extraction, limiting coverage to sentence-level context or fixed schemas; the hierarchical framework surfaces both strengths and concrete shortcomings of current LLMs when building KGs, informing where future extraction work should target.

**Key takeaways for KGF**: supports treating coreference and composite-mention decomposition as an explicit construction stage rather than folding it into a single flat extraction pass - directly relevant to the census stage's multi-level entity handling and to any redesign that separates mention resolution from schema-constrained triple extraction.

**Tags**: kg-construction, hierarchical-extraction, llm-evaluation, benchmark
**Source**: https://arxiv.org/abs/2510.11297 (PDF: `[paper] llms effective kg constructors, 2025.pdf`)
