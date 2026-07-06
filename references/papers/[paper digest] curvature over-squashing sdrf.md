**Understanding over-squashing and bottlenecks on graphs via curvature (2021)**

This paper introduces the curvature explanation of over-squashing: message-passing GNNs distort information flowing through structural bottlenecks, and those bottlenecks are exactly the negatively curved edges. It defines Balanced Forman Curvature (BFC), a combinatorial per-edge measure, proves negatively curved edges cause over-squashing, and proposes SDRF rewiring that improves node classification with minimal topology change.

**Key mechanism**
- Balanced Forman Curvature (BFC): edge-based combinatorial curvature from the triangles and 4-cycles supporting each edge
- Proof that negatively curved edges cause over-squashing
- SDRF (Stochastic Discrete Ricci Flow): adds edges around the most negatively curved edge, optionally removes positively curved ones

**Main findings**
- SDRF improves node classification on heterophilic/long-range benchmarks (Cornell, Texas, Wisconsin, Chameleon, citation graphs)
- Beats base GCN/GAT and prior rewiring with minimal topology change

**Key takeaways**
- Curvature localizes bottlenecks to individual edges
- BFC is cheap to compute per edge
- Rewiring is one use; the signal itself is the reusable part

**Relevance**
- BFC is a cheap per-edge signal over our 3,900 edges
- We do not need rewiring for depth (evidence <=2 hops) - we repurpose curvature as a classifier: negative BFC marks bridge edges where false SAME_AS closures hide, positive BFC marks triangle-dense candidate duplicate clusters

**Tags**
- #GraphCurvature #OverSquashing #GNN #Rewiring

**Source**
- Download: https://arxiv.org/pdf/2111.14522
- Local: [paper] curvature over-squashing sdrf, 2021.pdf
