**Forman Curvature for Complex Networks (2016)**

Forman's discretization of Ricci curvature, adapted to weighted and unweighted undirected networks, finds **negative curvature dominates most nodes and edges** in both model and real-world networks, with **significant negative correlation between Forman curvature and degree/centrality measures**. The curvature distribution is narrow in random and small-world networks but broad in scale-free and real networks, and Forman curvature is uncorrelated with clustering coefficient in most networks tested.

**Key mechanism**
- Adapts Forman's Ricci curvature discretization to undirected graphs (weighted and unweighted)
- Computed locally per edge from degree and shared-neighbor structure, no optimal-transport solve required
- Evaluated across model networks (random, small-world, scale-free) and real-world networks

**Main findings**
- Most nodes and edges carry negative Forman curvature across all network types studied
- Forman curvature correlates strongly and negatively with degree and centrality
- Forman curvature is largely uncorrelated with clustering coefficient
- Networks are vulnerable to targeted deletion of highly negative-curvature nodes

**Key takeaways**
- The degree-correlation finding is the load-bearing fact for KGF: on graphs where curvature tracks degree this tightly, a naive Forman signal is a degree proxy, not new structural information
- Grounds the H544 degree-ablation kill - if a curvature-based detector's discriminative power collapses once degree is controlled for, the detector was measuring degree, not topology
- Motivates seeking the non-degree residual (triangle terms, AFRC) rather than trusting plain Forman curvature alone

**Tags**
- #GraphCurvature #FormanRicci #ComplexNetworks #DegreeCorrelation

**Source**
- Download: https://arxiv.org/pdf/1603.00386
- Local: [paper] forman curvature complex networks, 2016.pdf
