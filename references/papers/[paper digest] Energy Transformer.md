**Energy Transformer, Hoover, Liang, Pham, Panda, Strobelt, Chau, Zaki, Krotov (IBM Research / Georgia Tech / RPI / MIT-IBM), NeurIPS 2023 (arXiv 2302.07253)**

The architecture that makes an entire transformer block one Hopfield network. A sequence of attention layers is designed so that each performs gradient descent on a **single engineered energy function** representing token relationships; the block including feed-forward, layer normalisation and residual connections is read as one large associative memory rather than attention alone.

**Key mechanism**
- Energy = a multi-head attention energy term (token-to-token routing) + a Hopfield network energy term over the hidden representation
- Forward pass = iterative energy descent, so depth becomes optimisation steps rather than distinct learned layers

**Main findings**
- Strong quantitative results on **graph anomaly detection and graph classification**, compared against GraphConsis, CARE-GNN, PC-GNN, BWGNN, MLP and Graph Transformer
- Also evaluated on masked image completion, where the energy-descent reading gives interpretable intermediate states

**Key takeaways**
- The most credible demonstration that a Hopfield-energy formulation applies to **graph-structured tasks** at all, though the tasks are node/graph classification, not retrieval
- Establishes that the useful unit is the whole block's energy, not a Hopfield layer bolted onto an existing pipeline - which is consistent with the CLOOB and Graph Hopfield ablations where the isolated memory term contributed little
- Provides the design language (engineered energy + descent) for any future energy-based retrieval formulation

**Tags**: #EnergyTransformer #Krotov #GraphTasks #EnergyDescent #R59

**Source**: https://arxiv.org/abs/2302.07253. Local: [paper] Energy Transformer, 2023.pdf
