**Graph Information Bottleneck for Subgraph Recognition (2020)**

This paper extracts the subgraph that is "as informative as possible yet with less redundant and noisy structure" - the IB-subgraph. It applies a GIB objective with an MI estimator adapted to irregular graphs, bi-level optimization, and a connectivity loss that stabilizes the extracted subgraph. The IB-subgraph shows superior structural properties versus attention and pooling baselines.

**Key mechanism**
- GIB objective with an MI estimator adapted to irregular graphs
- Bi-level optimization
- A connectivity loss stabilizes the extracted subgraph

**Main findings**
- Applications span classification improvement, interpretation, and denoising
- IB-subgraph shows superior structural properties vs attention/pooling baselines

**Key takeaways**
- A task-sufficient subgraph exists and is much smaller than the full graph
- Connectivity must be enforced or the extracted subgraph fragments
- Bi-level optimization signals that per-edge greedy may miss interacting edge sets

**Relevance**
- Closest mechanism to our thin 2-hop shell observation (100% within 2 hops, 91% on-seed) - predicts a task-sufficient subgraph much smaller than the full graph, and gives the recall-vs-edge-budget knee its theoretical basis
- The connectivity loss is directly relevant - our materialized subgraph must stay connected enough for 2-hop retrieval
- The bi-level formulation honestly signals naive per-edge greedy may miss interacting edge sets - the submodularity refuter must test this

**Tags**
- #InformationBottleneck #SubgraphSelection #GNN #Denoising

**Source**
- Download: https://arxiv.org/pdf/2010.05563
- Local: [paper] gib subgraph recognition, 2020.pdf
