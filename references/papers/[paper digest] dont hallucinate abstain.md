**Don't Hallucinate, Abstain: Identifying LLM Knowledge Gaps via Multi-LLM Collaboration**

This paper studies knowledge-gap detection and abstention in LLMs, proposing cooperative and competitive multi-LLM probing methods that beat the strongest single-model baseline by up to **19.3%** on abstain accuracy across three LLMs and four QA tasks spanning diverse knowledge domains.

Key mechanism:
- Adapts existing calibration/fine-tuning/prompting approaches as baselines, showing they fail via poor self-reflection and over-reliance on held-out calibration sets
- Introduces two novel model-collaboration mechanisms: LLMs probing other LLMs for knowledge gaps either cooperatively (models flag gaps for each other) or competitively (models are incentivized to expose each other's gaps)
- Evaluated on four QA tasks with diverse knowledge domains, including multi-hop reasoning

Main findings:
- Up to 19.3% improvement in abstain accuracy over the strongest single-model baseline
- Self-reflection alone is unreliable for gap detection - models are poor judges of their own knowledge limits
- The collaboration signal also helps pinpoint failure cases in retrieval augmentation and locate knowledge gaps specifically within multi-hop reasoning chains

Key takeaways (relevance to KGF): gap detection via multi-model probing is a stronger abstention signal than single-model self-reflection, directly informing H272/H580's design of abstention as a first-class citizen feeding a repair queue. The multi-hop finding is particularly relevant - KGF's graph traversal is inherently multi-hop, and this paper shows knowledge gaps concentrate there, reinforcing the case for gap-ledger entries triggered at hop boundaries rather than only at final-answer time.

Tags: knowledge-gaps, abstention, multi-llm-collaboration, calibration, multi-hop-qa

Source: https://arxiv.org/abs/2402.00367
