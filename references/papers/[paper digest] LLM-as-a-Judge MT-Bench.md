# Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena

**Authors**: Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang, Joseph E. Gonzalez, Ion Stoica (UC Berkeley, LMSYS)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2306.05685

**Publication date**: 2023-06 (NeurIPS 2023 Datasets & Benchmarks)

## Summary

- The reference measurement of LLM-judge reliability: 3K expert votes (MT-Bench) + 30K crowd votes (Chatbot Arena); GPT-4 judge vs human agreement **85%** (non-tie setup) - HIGHER than human-human agreement (**81%**); humans shown GPT-4's dissenting judgment deem it reasonable in 75% of cases and switch in 34%
- Agreement is delta-dependent: rises from **~70% to ~100%** as the performance gap between compared systems widens - judges are reliable on large deltas, coin-flip-adjacent on small ones
- **Position bias**: only GPT-4 stays consistent in > 60% of judgments when answer order is swapped; other judges strongly favor position one; few-shot examples raise GPT-4 swap-consistency from **65.0% → 77.5%**; conservative fix = score both orders, count disagreement as a tie
- **Verbosity bias**: a repetition attack (longer, no-new-information answers) fools all judges except GPT-4; self-enhancement bias and weak math grading also cataloged
- Single-answer grading (absolute score, no pairing) matches pairwise ranking well for GPT-4 - a stable internal rubric - but is noisier for weaker judges

**Relevance to Knowledge Graph Foundry**: quantifies the judge AS an instrument: 15% disagreement with the human majority at the frontier tier, 19% human-human disagreement as the ceiling, and reliability that DEGRADES exactly in the regime KGF cares about (small deltas between config-adjacent pipelines). The delta-dependence finding is the core argument that judge-based continuous metrics need either rectification (PPI) or restriction to supporting-evidence roles - a judge that agrees 70% on close pairs contributes noise comparable to the effect being measured. Swap-order consistency and few-shot anchoring are cheap variance-reduction levers for KGF's generative judge scores (currently unreplicated 5-point ordinals).

**Tags**: llm-judge, inter-rater-agreement, position-bias, verbosity-bias, instrument-noise, evaluation-reliability
