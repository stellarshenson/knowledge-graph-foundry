# A New Query Expansion Approach for Enhancing Information Retrieval via Agent-Mediated Dialogic Inquiry (AMD)

**Source**: https://arxiv.org/abs/2502.08557
**Authors**: Wonduk Seo, Hyunjin An, Seunghyun Lee (Enhans)
**Venue/Date**: SIGKDD 2025 Agent4IR Workshop, February 2025 (v3 Aug 2025)

## Summary

AMD is a multi-agent query expansion framework that reformulates a query into Socratic sub-questions, generates pseudo-answers, and filters them with a reflective feedback agent before retrieval. On six BEIR datasets and TREC DL 2019/2020 it consistently beats prior LLM query-expansion methods (Q2D, Q2C, GenQREnsemble, GenQRFusion) across sparse, dense, and RRF retrieval.

## Method

- Socratic Questioning Agent reformulates the initial query into three sub-questions along clarification, assumption-probing, and implication-probing dimensions (single LLM inference)
- Dialogic Answering Agent generates one pseudo-answer per sub-question as a surrogate document (parallel, single inference)
- Reflective Feedback Agent evaluates and selectively rewrites the pseudo-answers, dropping vague/redundant/irrelevant content (non-finetuned LLM)
- Refined answers integrated via sparse concatenation, weighted dense embedding fusion (0.7 initial + 0.3 answers), or reciprocal rank fusion
- Backbone: Qwen2.5-7B-Instruct; dense encoder multilingual-e5-base

## Key Findings

- Outperforms baselines on nearly all datasets/metrics (nDCG@10, R@1000) with statistically significant gains (p<0.05, Holm-Bonferroni)
- Uses only three targeted sub-questions vs GenQREnsemble/GenQRFusion's up to 10 prompt inferences, cutting cost
- Ablation: the Reflective Feedback Agent improves average score and reduces variance/noise
- Even without the feedback module, AMD still beats prior baselines

## Relevance to KGF

- SUPPORTS H30 (question-native graph): generating and refining explicit sub-questions as first-class retrieval artifacts materially improves retrieval, evidence that question representations carry retrieval value beyond raw entities
- The Socratic decomposition is a candidate ingest-time process for populating answerable-question nodes and linking them to evidence
- The generate-then-reflect loop (answering agent + feedback agent) mirrors KGF's self-auditing repair pattern - produce, critique, keep only high-quality content
