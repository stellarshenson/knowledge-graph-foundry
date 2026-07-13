**Augmentations of Forman's Ricci Curvature and their Applications in Community Detection (2024, J. Phys. Complexity)**

Augmented Forman-Ricci curvature (AFRC), which adds triangle counts to plain Forman curvature, is shown to give **sufficient insight into network structure for community detection**, and the resulting **AFRC-based community detection algorithm is competitive with Ollivier-Ricci-curvature (ORC) based approaches** at a fraction of the computational cost.

**Key mechanism**
- Augments Forman-Ricci curvature with triangle counts (2-dimensional simplicial complexes), producing AFRC
- Empirically and theoretically compares AFRC against both Ollivier-Ricci curvature and un-augmented Forman-Ricci curvature
- Builds a novel AFRC-based community detection algorithm using this augmented signal

**Main findings**
- AFRC frequently carries enough structural information to substitute for ORC in community detection tasks
- AFRC-based community detection is competitive with ORC-based methods
- AFRC is computationally cheaper than ORC-based approaches, avoiding the optimal-transport solve ORC requires per edge

**Key takeaways**
- Confirms the triangle-bonus term (not the degree term) is precisely the information-beyond-degree component that plain Forman curvature lacks
- Isolating the triangle bonus gives KGF a way to separate "curvature signal that is really just degree" from "curvature signal that reflects genuine local density/community structure"
- Practical for KGF at bench-ladder scale: cheap to compute, no optimal-transport solve, applicable as a community-boundary or duplicate-cluster detector once the degree confound is controlled for (per H544)

**Tags**
- #GraphCurvature #FormanRicci #AFRC #CommunityDetection

**Source**
- Download: https://arxiv.org/pdf/2306.06474
- Local: [paper] afrc community detection, 2024.pdf
