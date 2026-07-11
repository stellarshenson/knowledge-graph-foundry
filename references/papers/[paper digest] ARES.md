# ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems

**Authors**: Jon Saad-Falcon, Omar Khattab, Christopher Potts, Matei Zaharia (Stanford, Databricks)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2311.09476

**Publication date**: 2023-11-16 (NAACL 2024)

## Summary

- Three-stage judge pipeline: (1) generate synthetic in-domain query/answer triples from the corpus, (2) fine-tune lightweight DeBERTa-v3-large classifier judges for context relevance / answer faithfulness / answer relevance, (3) score RAG systems and rectify with **prediction-powered inference (PPI)** using a small human preference validation set of **~150-300 labels** - producing confidence intervals, not point scores
- Ranking fidelity across KILT + SuperGLUE mock RAG systems: mean Kendall tau **0.91** (context relevance) / **0.97** (answer relevance); beats RAGAS by **+0.065 / +0.132** tau and per-triple judge accuracy by **+59.9 / +14.4 points**
- Label efficiency: beats a 1,350-annotation direct-sampling baseline by 0.08 tau while using **78% fewer annotations**; PPI improves the fine-tuned judge's ranking in every dataset tested
- Label-budget cliff (Table 3): tau holds at 200-400 labels, collapses at 50 labels (**0.44-0.67**) - ~150 labels is the floor for valid rectification
- Swapping human labels for GPT-4-generated labels costs **0.05-0.30 tau** - frontier-model gold labels are a measurably degraded substitute

**Relevance to Knowledge Graph Foundry**: the proof that judge-based metrics become INSTRUMENTS only when paired with a rectifier and confidence intervals - point-score judging (RAGAS-style) ranks systems measurably worse. The 150-300 label budget is the concrete price of a calibrated judge metric for KGF's faithfulness/answerability axes; KGF already owns adjudicated label sets (298 identity pairs, 63 deterministic checks) that can seed the PPI validation split. Kendall-tau-on-system-rankings is also the right meta-metric for validating any new KGF instrument against the harness it replaces.

**Tags**: rag-evaluation, llm-judge, prediction-powered-inference, confidence-intervals, label-efficiency, fine-tuned-judge
