# Can LLMs be Good Graph Judge for Knowledge Graph Construction? (GraphJudge)

**Authors**: Haoyu Huang, Chong Chen, Zeang Sheng, Yang Li, Wentao Zhang (HKUST, Huawei Cloud, Peking University)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2411.17388

**Publication date**: 2024-11-26 (first arXiv version)

## Summary

- Three-module KG-construction framework attacking noise, domain inaccuracy, and hallucination: (1) **Entity-Centric Text Denoising (ECTD)** - extract entities first, then rewrite the document keeping only entity-relevant content before triple extraction, (2) **Knowledge-Aware Supervised Fine-Tuning** - fine-tune a 7B LLM on the graph-judgement task to **over 90% judgement accuracy**, (3) **Graph Judgement** - the fine-tuned judge classifies every generated triple true/false against the denoised source before it enters the graph
- Defines graph judgement as a first-class task: per-triple binary verification with the source document as context - triple-level provenance-checked admission, not post-hoc cleanup
- SOTA F1 on two general text-graph benches (REBEL, GenWiki) and one domain-specific set; explicitly beats higher-recall/lower-precision rivals (RAKG, PiVe) on F1 - the paper's position is that unverified recall is not quality
- Efficiency claim: a fine-tuned 7B judge + GPT-4o-mini extractor outperforms GPT-4o extraction alone - verification is cheaper than a bigger extractor
- Generalizes across corpora without re-tuning the judge (their Table 3 cross-corpus results)

**Relevance to Knowledge Graph Foundry**: The published form of admission-time trustworthiness: every edge is judged against source before commit. KGF has NO per-triple verification gate - extraction output enters the graph unjudged, and fidelity is only probed downstream. GraphJudge's precision-first stance is the exact tension with KGF's coverage mandate ("miss nothing"): a judge gate raises precision but its false rejections ARE missed information - the precision/coverage frontier for admission gates is unmeasured in both systems.
