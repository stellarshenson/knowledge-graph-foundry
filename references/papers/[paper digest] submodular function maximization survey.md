**Submodular Function Maximization (2014) | Krause, Golovin**

This survey unifies the theory and algorithms for maximizing submodular set functions, whose defining property is diminishing returns - the marginal gain of adding an element to a set is at least its gain when added to any superset. For monotone submodular functions under a cardinality constraint, greedy achieves the tight **(1-1/e) ~ 0.632** approximation, and local search with improving single swaps terminates at a certified local optimum.

**Key mechanism**
- Submodularity: marginal gain of adding x to A >= its gain added to any superset (diminishing returns)
- Greedy achieves the tight (1-1/e) ~ 0.632 approximation under a cardinality constraint (Nemhauser-Wolsey-Fisher 1978)
- Lazy/CELF and stochastic greedy preserve the bound
- Local search with improving single swaps terminates at a certified local optimum

**Main findings**
- (1-1/e) ~ 0.632 tight bound for monotone submodular under cardinality constraint
- Single-swap local optimum is ~1/2 unconstrained, degraded under matroid constraints

**Key takeaways**
- Submodularity is the property that makes a swap-stable fixed point a rigorous certificate
- Strong positive interactions (supermodularity) break single-edit certificates
- Lazy and stochastic variants keep the guarantee at lower cost

**Relevance**
- The exact mathematics behind "certify no single edit improves" - if a foundry potential is monotone submodular, greedy edit-selection carries a provable guarantee and the swap-stable fixed point is a rigorous "improvement still possible = false" certificate
- Equally delimits the failure mode: strong positive interactions (supermodularity) invalidate single-edit certificates - the precise refuter to run

**Tags**
- #Submodular #Optimization #GreedyAlgorithms #Certificates

**Source**
- Download: https://viterbi-web.usc.edu/~shanghua/teaching/Fall2023-670/krause12survey.pdf
- Local: [paper] submodular function maximization survey, 2014.pdf
