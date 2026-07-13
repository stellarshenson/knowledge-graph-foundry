**OPI: Ontology-Guided Evidence Path Inference for Multi-hop Knowledge Graph Question Answering (2026)**

Multi-hop KGQA methods typically expand outward from the topic entity with no constraint on where the path should end, so the candidate set explodes combinatorially and fills with type-incompatible noise (a path from "Lionel Messi" branches into countries, clubs, awards, and languages alike). OPI's shift is to predict the answer's *type* first and use a compact type-level ontology graph to constrain the final hop before expansion runs wild, then run an iterative generator-refiner loop over the surviving paths. Against the strongest prior KG+LLM baselines, OPI improves Hit@1/F1 by **4.6/5.0 points on WebQSP** and **8.9/3.3 points on CWQ**, and its retrieval-only variant hits **near-saturated Hit@1 on MetaQA (100.00/99.99/99.96 across 1/2/3-hop)**.

**Key mechanism**
- Ontology graph O = (C, R, S): type-level relation signatures (c_head, r, c_tail), built from explicit schema predicates (Freebase) or induced from training-data type statistics (Wiki-Movie)
- Answer-type prediction: a fine-tuned LLaMA2-7B predicts the answer's semantic type c_a from the question, supervised by tail types reachable via the gold path's last-hop relation
- Bidirectional retrieval: unconstrained forward prefix expansion meets a constrained final hop restricted to relations ending in type c_a - the two sides meet at the penultimate node, collapsing the final-hop candidate set to one or a few relations, reducing search from O(b^x) to O(b^(x-1) * beta(c_a))
- Iterative generator-refiner loop: a generator proposes an answer, a refiner critiques it with structured feedback (retained/forbidden answers, prioritized/dropped paths); stops on high confidence or answer stability (max 3 rounds)
- Fallback: reverts to plain topic-centered retrieval if no answer type maps to any final-hop relation

**Main findings**
- Main comparison (best-of-two OPI variants): **92.3 Hit@1 / 76.8 F1 on WebQSP**, **76.5 Hit@1 / 62.7 F1 on CWQ** - beats ORT/GCR/UniKGQA-class baselines across the board
- Retrieval-only ablation (OPI-BR): Hit@1 of **95.39 (WebQSP)** and **88.95 (CWQ)**, ahead of reproduced RoG-BR and GCR-BR - but F1 trails (39.09 vs GCR-BR's 58.03) since type-compatible endpoints aren't yet question-verified
- Removing the type-level search space costs the most: Hit@1/F1 drop **10.19/13.95 points (WebQSP)** and **22.37/18.54 points (CWQ)**
- Moving the type constraint from in-retrieval to post-retrieval filtering costs F1 **8.16 points (WebQSP)** and **13.98 points (CWQ)** - constraints must gate expansion, not filter after the fact
- Removing iterative refinement raises recall but drops F1 (CWQ 59.59 -> 56.42) - refinement is a precision filter, not a recall booster
- Ontology construction is cheap: the Freebase ontology (32,195 signatures) builds in ~1.93h and covers 99.7%+ of benchmark relations; schema-free Wiki-Movie induction takes 1.17s

**Key takeaways**
- Constraining only the *final hop* by predicted answer type is enough to collapse path explosion without sacrificing recall; the ontology abstraction only needs to be coarse and stable, not exhaustive
- Answer-type prediction is a lower-variance target than direct answer prediction, making it a cheap, reusable retrieval-time signal
- Type constraints must gate expansion in-loop; post-hoc filtering over an already-pruned set cannot recover lost paths
- Typed retrieval and answer refinement solve different problems (reachability vs precision) - typed structure alone is not sufficient for full answer-set correctness

**Relevance**
- Closest published analogue to R50-H592's typed-relation-weighted PPR walk; its ablation (type-level search space is the single largest lever) is a useful prior for R50's acceptance bar
- Caveat: OPI's ontology assumes a clean, near-complete Freebase-style schema; KGF's self-extracted relation vocabulary is far higher-entropy (H395: 334 types, entropy 6.22; H107 variance), so the "collapse to one relation" effect may not transfer without first taming vocabulary noise

**Tags**
- #KGQA
- #TypedRetrieval
- #MultiHop
- #OntologyGraph
- #PathInference

**Source**
- Download: https://arxiv.org/abs/2606.28076
- Local: [paper] OPI ontology-guided evidence path inference, 2026.pdf
