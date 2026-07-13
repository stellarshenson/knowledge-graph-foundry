**SR: Subgraph Retrieval Enhanced Model for Multi-hop Knowledge Base Question Answering (2022)**

Prior trainable KBQA retrievers (PullNet, IRN, UHop) interleave retrieval and reasoning step by step, forcing the reasoner to train and infer on partial, intermediate subgraphs where the "correct" intermediate state is usually unobserved - this injects bias that compounds across hops. SR's shift is to fully decouple the retriever from the reasoner: SR is trained as an efficient dual-encoder path-expander that produces one finished subgraph, and *any* subgraph-oriented reasoner (GRAFT-Net, NSM) then reasons once over the complete result. The retriever is estimated by the coverage-vs-noise curve directly: at a fixed subgraph size, SR's answer coverage rate is significantly higher than the standard personalized-PageRank (PPR) heuristic, and swapping SR into NSM improves QA Hits@1 by **0.4-9.7 points and F1 by 1.3-8.7 points** over other retrieval methods, setting a new state of the art for embedding-based KBQA.

**Key mechanism**
- Probabilistic decoupling: p(a|G,q) = sum_G p_phi(a|q,G) * p_theta(G|q) - the retriever and reasoner are separately trainable terms, so the retriever can be pre-trained and fine-tuned independently before the reasoner ever sees a subgraph
- Path expansion: a RoBERTa dual-encoder scores each candidate outgoing relation r by dot product s(q,r) = f(q)^T h(r); the question embedding is updated at each step by concatenating the original question with all relations selected so far
- Learned stopping: a virtual "END" relation competes in the same scoring space - expansion halts automatically when END outscores every real relation, avoiding a fixed hop-depth hyperparameter
- Subgraph induction/merge: top-K beam-searched paths per topic entity are instantiated into trees, then trees from different topic entities are merged at shared entities - multiple topic entities act as mutual constraints that shrink the final subgraph
- Weakly supervised pre-training: all shortest KG paths from topic entity to gold answer are extracted as multi-path supervision, since ground-truth subgraphs are unavailable
- End-to-end fine-tuning: after pre-training, the reasoner's answer likelihood feeds back into the retriever's prior distribution, jointly improving both

**Main findings**
- Main comparison: SR+NSM reaches **68.9 Hits@1 / 64.1 F1 on WebQSP** and **50.2 Hits@1 / 47.1 F1 on CWQ**, setting new SOTA among embedding-based KBQA models
- Coverage-vs-size curve: NSM's Hits@1 *drops* once the retrieved subgraph exceeds ~5,000 nodes despite higher raw answer coverage - a bigger subgraph is not simply better once noise outweighs completeness
- Component ablation: removing the question-update mechanism costs Hits@1 **4.3-15.0 points**; a fixed hop depth instead of learned stopping costs **2.1-18.5 points**
- Subgraph merging (mutual topic-entity constraints) shrinks average CWQ subgraph size from 204 to 174 nodes at effectively no QA cost
- Unsupervised pre-training (100,000 pseudo instances, for scarce QA pairs) improves the untrained retriever by about **20 points of Hits@10 answer-coverage**
- End-to-end fine-tuning lifts retrieval Hits@1 by **2-10.6 points** and downstream QA Hits@1 by up to **0.6-2.5 points**

**Key takeaways**
- Decoupling retrieval from reasoning removes the partial-subgraph training bias in prior trainable retrievers, and is plug-and-play: the same retriever slots into different reasoners (GRAFT-Net or NSM) with consistent gains
- Subgraph size is a precision/recall knob with a real optimum - past a threshold, more retrieved nodes actively hurt downstream QA accuracy even as coverage keeps climbing
- Multiple topic entities can be treated as *mutual structural constraints* (tree-merge at shared entities) rather than independently expanded and unioned
- Weak supervision from shortest KG paths is sufficient to bootstrap a competitive trainable retriever; end-to-end fine-tuning against reasoner feedback improves it further without new labels

**Relevance**
- SR is the retrieval-half analogue in the "KGQA lineage (OPI/RoG/SR)" R50 cites as its structural-axis reference class; the coverage-vs-subgraph-size curve and the mutual-topic-entity merge mechanism bear directly on R50-H591's region-mass/gating hypothesis and R50-H593's two-slot comparison-class seeding
- Contrast point for R50's FENCE constraint (constructions must fuse into the existing dense+PPR region, not compete for seed slots): SR's decoupling works well specifically because the retriever is trained end-to-end against the reasoner - which R50's frozen-probe design (H541) does not attempt this round

**Tags**
- #KGQA
- #SubgraphRetrieval
- #MultiHop
- #DecoupledRetrieval
- #WeakSupervision

**Source**
- Download: https://arxiv.org/abs/2202.13296
- Local: [paper] SR subgraph retrieval multi-hop KBQA, 2022.pdf
