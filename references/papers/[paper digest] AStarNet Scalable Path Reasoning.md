**A*Net: A Scalable Path-based Reasoning Approach for Knowledge Graphs (2023, NeurIPS)**

A*Net makes learned path reasoning (NBFNet-style) tractable at scale by learning a PRIORITY function - an A*-style heuristic that selects only the important nodes and edges to expand at each iteration. It visits **merely 10% of nodes and 10% of edges** per step, is the first path-based method to scale to **ogbl-wikikg2 (2.5M entities, 16M triples)**, sets a new SOTA there, and converges faster than embedding methods.

**Key mechanism**
- NBFNet path-reasoning backbone (learned Bellman-Ford operators over relation paths)
- A learned priority function ranks frontier nodes/edges; only the top fraction is expanded (learned pruning of the exponential path space)
- Analogous to A* search: priority = learned estimate of a node's usefulness toward the target

**Main findings**
- 10% node / 10% edge visitation per iteration with competitive accuracy
- First path-based reasoner to run on million-scale ogbl-wikikg2; new SOTA
- Faster convergence than embedding methods

**Key takeaways**
- The learned priority function is a "PPR with a brain" - a trained analogue of PPR's mass concentration
- Scalability is the headline contribution; accuracy parity with NBFNet is retained, not exceeded
- Still supervised per relation vocabulary (like NBFNet)

**Relevance**
- A*Net's learned priority is the natural learned competitor to H592's typed-PPR walk - both concentrate exploration on relation-relevant frontier
- The honest KGF read: at 6,626 entities SCALE is not KGF's constraint (PPR is already cheap), so A*Net's headline advantage is moot; the only question is whether its learned priority beats isotropic PPR, and that needs training labels KGF lacks (n~132)
- Confirms the pattern: the learned methods buy scale, not per-query accuracy over PPR at small graph size

**Tags**
- #PathReasoning #Scalability #KnowledgeGraph #LearnedPriority

**Source**
- Download: https://arxiv.org/pdf/2206.04798
- Local: [paper] AStarNet Scalable Path Reasoning, 2023.pdf
