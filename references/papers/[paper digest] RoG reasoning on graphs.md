**RoG: Reasoning on Graphs - Faithful and Interpretable Large Language Model Reasoning (2024)**

LLMs reasoning without grounding hallucinate plausible-sounding but wrong intermediate steps (the paper's running example: an LLM invents "Justin Bieber has a daughter named Allie" when asked who his brother is). RoG's shift is to make the LLM's *plan* itself KG-grounded before any retrieval happens: instead of retrieving triples first and reasoning over them, RoG prompts an LLM to generate candidate **relation paths** (sequences of relation names with no entities), verifies which ones are actually instantiable in the KG, then reasons only over the resulting grounded reasoning paths. This planning-retrieval-reasoning framework achieves **85.7 Hit@1 / 70.8 F1 on WebQSP** and **62.6 Hit@1 / 56.2 F1 on CWQ**, beating UniKGQA by **22.3% Hit@1 / 14.4% F1 on CWQ**, and its planning module alone lifts an unmodified Flan-T5's Hit@1 by **119.3%** when plugged into a separate LLM's inference.

**Key mechanism**
- Relation paths z = {r1,...,rl} (relation names only, no entities) serve as faithful "plans" - relations are far more stable over time than entity facts, so a plan stays valid as entity data updates
- Planning optimization: an LLM is instruction-tuned to generate KG-grounded relation paths, supervised by minimizing KL divergence to the posterior over shortest KG paths connecting the question entity to the gold answer entity
- Retrieval: given a generated relation path, constrained BFS retrieves every instantiated reasoning path in the KG that follows exactly that relation sequence from the topic entity
- Reasoning: an LLM fine-tuned under the FiD (fusion-in-decoder) framework reads the retrieved reasoning paths and generates an explained answer, rather than majority-voting the endpoints
- Planning and reasoning share one LLaMA2-Chat-7B backbone trained jointly via a combined ELBO objective; the trained planning module plugs into *any other* LLM at inference (ChatGPT, Alpaca, Flan-T5) without retraining it

**Main findings**
- Main comparison: **85.7 Hit@1 / 70.8 F1 on WebQSP**, **62.6 Hit@1 / 56.2 F1 on CWQ** - beats DECAF by **4.4% Hit@1 (WebQSP)** and UniKGQA by **22.3% Hit@1 / 14.4% F1 (CWQ)**
- w/o planning (bare LLM, no KG retrieval): F1 collapses to 49.69/33.76, confirming planning is what supplies KG grounding
- w/o reasoning (majority-vote over retrieved paths): recall rises to 79.85% but precision collapses to 46.90, net F1 drops to 49.56/22.26
- w/ random plans (random KG walks instead of learned paths): F1 35.24/37.64 - *worse* than removing planning entirely, i.e. a bad plan is worse than no plan
- Plug-and-play transfer: attaching the planning module to other LLMs lifts Hit@1 by **8.5% (ChatGPT)**, **15.3% (Alpaca-7B)**, and **119.3% (Flan-T5-xl, 30.95 -> 67.87)** with zero retraining
- Top-K relation-path sweep: recall grows monotonically with K, but F1 plateaus and precision degrades past K=3, motivating that cutoff

**Key takeaways**
- Separating the relation-level plan from instance-level retrieval lets an LLM plan without hallucinating facts, since the plan is checked against the KG before retrieval commits
- An ungrounded plan is actively harmful, worse than no plan - the value comes specifically from KG-grounding it
- The planning module transfers zero-shot to other LLMs because it only hands over retrieved-path text as context, decoupling the trained component from the reasoning LLM's own weights
- Retrieval breadth (K) has a precision/noise optimum, not a monotonic-better relationship with answer quality

**Relevance**
- RoG's planning-retrieval-reasoning split is the load-bearing precedent R50 cites directly (R50's text names the "KGQA lineage OPI/RoG/SR" as its structural-axis reference class); the random-plan-worse-than-none finding is a direct caution for R50-H587's contrarian axis-killer
- Caveat: RoG trains against Freebase's clean, stable relation set; KGF's self-extracted vocabulary is far higher-entropy (H395: 334 types, entropy 6.22), so "relations are stable" may not hold as cleanly

**Tags**
- #KGQA
- #FaithfulReasoning
- #RelationPaths
- #LLMPlanning
- #TypedRetrieval

**Source**
- Download: https://arxiv.org/abs/2310.01061
- Local: [paper] RoG reasoning on graphs, 2024.pdf
