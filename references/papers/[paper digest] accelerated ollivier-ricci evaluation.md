**Accelerated Evaluation of Ollivier-Ricci Curvature Lower Bounds: Bridging Theory and Computation (2024)**

Ollivier-Ricci curvature (ORC) measures edge curvature via Wasserstein distance between neighbor distributions - accurate but expensive, and prior lower-bound work (Jost-Liu) extended to hypergraphs by Coupette, Dalleiger and Rieck still hit computational walls. This paper simplifies the Jost-Liu lower bound to a linear-complexity method, making ORC lower-bound evaluation tractable on large-scale networks and hypergraphs.

**Key mechanism**
- Extends Jost-Liu's ORC lower bound (via the Wasserstein distance upper bound) to discrete spaces with integer metrics, i.e. hypergraphs
- Replaces the prior hypergraph ORC approach's heavier computation with a simplified linear-complexity procedure

**Main findings**
- Simulations on synthetic and real-world datasets show significant speed improvements evaluating ORC versus prior hypergraph methods
- Linear complexity holds while preserving the lower-bound's descriptive validity

**Key takeaways**
- Full transport-based ORC remains the reference signal but stays costly even with this lower-bound speedup, versus Forman's O(1) per-edge cost
- Documents concretely why an optimal-transport-based curvature signal is the wrong default instrument at KGF's scale, and why Forman/AFRC is the pragmatic substitute
- Relevance to KGF: grounds the project's choice of Forman-family curvature over Ollivier-Ricci as the working instrument - even the accelerated ORC lower bound is heavier than a single AFRC pass

**Tags**
- #GraphCurvature #OllivierRicci #Hypergraph #ComputationalComplexity

**Source**
- Download: https://arxiv.org/pdf/2405.13302
- Local: [paper] accelerated ollivier-ricci evaluation, 2024.pdf
