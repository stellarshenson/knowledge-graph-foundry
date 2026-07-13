**Mixing Patterns in Networks**

Newman formalizes assortative mixing with a single closed-form coefficient: for discrete vertex types, **r = (Tr e − ‖e²‖) / (1 − ‖e²‖)**, and for scalar attributes (including vertex degree) the standard Pearson correlation **r = Σxy xy(e_xy − a_x b_y) / (σ_a σ_b)**, both computable directly from the joint edge-endpoint distribution e_ij without simulation. Real-network degree assortativity r ranges from +0.363 (physics coauthorship) to −0.326 (freshwater food web), with social networks generally assortative and technological/biological networks generally disassortative.

**Key mechanism**: the coefficient is a ratio of power-sums (moments) over the joint distribution of edge-endpoint attributes - Σeii, Σaibi for discrete types, or Σxy·exy, Σx·ax, Σy·by, variances for scalar types. Because each term is a sum over edges, r can be updated incrementally: adding or removing an edge only changes the running power-sums it touches, giving an exact O(1) update per edge rather than a full recomputation over the graph.

**Main findings**: assortative mixing is pervasive and domain-patterned - social networks (coauthorship, actor collaboration, corporate boards, friendship) are assortative by degree; technological networks (Internet AS graph, WWW, power grid) and biological networks (protein interaction, food webs) are disassortative. Assortativity by degree measurably changes network resilience: assortative networks are more robust to targeted removal of high-degree vertices, disassortative networks less so. Generating-function models reproduce these effects analytically and via Monte Carlo.

**Key takeaways for KGF**: the closed-form power-sum structure is directly exploitable as a streaming ingest-time signal - each entity/relation insertion updates the running moments (Σeii, Σaibi, or Σxy, Σx, Σy, σa, σb) in O(deg) time, giving an always-current assortativity coefficient for entity-type or degree mixing patterns without recomputing over the whole graph. This is a structural companion to KGF's existing scalar drift channels (JSD-CUSUM), usable to detect when the graph's connectivity pattern between types shifts as ingestion proceeds.

Tags: network-science, assortativity, closed-form, streaming-metric, incremental-update, graph-structure

Source: https://arxiv.org/abs/cond-mat/0209450 (M.E.J. Newman, Phys. Rev. E 67, 026126, 2003)
