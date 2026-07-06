**Graph Information Bottleneck (2020)**

Graph Information Bottleneck (GIB) learns graph representations that are both expressive and robust by extending the Information Bottleneck to graphs: maximize task relevance I(Z;Y) while minimizing input compression I(Z;G) over both structure and features. Two tractable variational instantiations inject structural sampling layer-by-layer, yielding **up to 31%** robustness improvement under adversarial perturbation at retained accuracy.

**Key mechanism**
- Extend Information Bottleneck to graphs: maximize I(Z;Y) (task relevance), minimize I(Z;G) (input compression) over structure and features
- Two tractable variational instantiations (GIB-Cat, GIB-Bern) inject a structural sampling layer-by-layer

**Main findings**
- Up to 31% robustness improvement under adversarial structure/feature perturbation vs SOTA GNN defenses
- Robustness gained at retained accuracy

**Key takeaways**
- Formalizes keeping only edges that carry task information
- With gold evidence the intractable I(Z;G) collapses to a countable coverage term
- A minimal sufficient subgraph is the right target

**Relevance**
- Formalizes "keep only edges that carry task information", which our probe set makes concrete
- The beta-weighted trade-off I(Z;Y) - beta*I(Z;G) maps onto Phi_task = probe-sufficiency - lambda*token-cost; with gold evidence the intractable I(Z;G) collapses to a countable coverage term (edges whose removal breaks a gold path) - GIB's benefit without neural MI estimation
- Theoretical warrant that a minimal sufficient subgraph is the right target

**Tags**
- #InformationBottleneck #GNN #Robustness #SubgraphSelection

**Source**
- Download: https://arxiv.org/pdf/2010.12811
- Local: [paper] graph information bottleneck, 2020.pdf
