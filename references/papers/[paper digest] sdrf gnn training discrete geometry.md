**Rewiring Networks for Graph Neural Network Training Using Discrete Geometry (2022)**

Topping et al. (2021) introduced Balanced Forman Curvature (BFC) and SDRF rewiring as the state-of-the-art fix for over-squashing but BFC is expensive to compute. This paper swaps BFC for three classical discrete curvature notions - 1D Forman, Augmented Forman, and Haantjes - inside the same SDRF rewiring loop, and shows they match or approach BFC's accuracy gains on 12 real-world graphs while running **orders of magnitude faster**, with the largest datasets triggering out-of-memory errors for BFC but not for the classical curvatures.

**Key mechanism**
- SDRF (Stochastic Discrete Ricci Flow) loop unchanged from Topping et al.: repeatedly find the most negatively curved edge, add an edge around it to relieve the bottleneck, optionally remove a positively curved edge elsewhere
- Only the curvature functional plugged into SDRF changes - 1D Forman curvature (fastest, purely combinatorial), Augmented Forman curvature (adds triangle counts, slower but closer to BFC's discriminative power), Haantjes curvature (differential-geometric analogue)
- All three avoid BFC's need to enumerate 4-cycles around each edge, which is the source of its cost blowup on dense graphs

**Main findings**
- On heterophilic graphs, classical curvatures beat "no rewiring" by wide margins: Cornell 48.5% -> 55-58%, Texas 59.2% -> 63-68%, Wisconsin 50.2% -> 52-56% (Table 3, 95% CI over 100 seeds)
- BFC still edges out the classical curvatures on several homophilic benchmarks (Cora, Citeseer) but throws OOM on Pubmed and Coauthor CS where the classical curvatures complete successfully
- Reference BFC (Topping et al.'s own numbers) generally beats this paper's reproduction of BFC and the classical curvatures on heterophilic sets, but the gap narrows once dataset scale grows
- Runtime: 1D Forman and Haantjes are consistently the fastest to compute; Augmented Forman is the slowest of the three classical options but still far cheaper than BFC at scale, except on the densest graphs (Computers, Photo) where BFC can be faster

**Key takeaways**
- Curvature-based rewiring is not a single BFC-shaped hammer - simpler, cheaper curvature notions recover most of the accuracy benefit
- The accuracy/cost tradeoff flips with graph density: pick the curvature by scale, not by a single "best" choice
- BFC's exact discriminative power matters most on small, homophilic graphs; classical curvatures are the pragmatic choice once graphs get big enough that BFC OOMs

**Relevance**
- Confirms the KGF curvature-as-classifier repurposing (see the existing AFRC and BFC digests) rests on a paper-validated family, not one bespoke metric - if BFC/AFRC signals underperform on larger graph rungs, 1D Forman or Haantjes are drop-in, cheaper alternatives already benchmarked at this scale
- The repair analogy holds directly: SDRF's "add edges at the most negatively curved edge" is the mechanical template for a repair-at-ingest pass that adds context/links around negatively-curved answer neighborhoods

**Tags**
#GraphCurvature #OverSquashing #GNN #Rewiring #SDRF

**Source**
- Download: https://arxiv.org/pdf/2207.08026
- Local: [paper] sdrf gnn training discrete geometry, 2022.pdf
