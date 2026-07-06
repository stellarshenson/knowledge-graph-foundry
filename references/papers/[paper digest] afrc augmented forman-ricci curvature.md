**Mitigating Over-Smoothing and Over-Squashing using Augmentations of Forman-Ricci Curvature (2023)**

Ollivier-Ricci rewiring is accurate but needs an optimal-transport solve per edge. AFRC augments plain Forman curvature with triangle (optionally 4-cycle) counts, recovering Ollivier-Ricci's discriminative power in linear time. Low-curvature edges are added and high-curvature edges removed, fixing over-squashing and over-smoothing jointly, at a fraction of the compute.

**Key mechanism**
- Add triangle (optionally 4-cycle) counts to plain Forman curvature
- Recovers Ollivier-Ricci's discriminative power in linear time
- Add low-curvature edges, remove high-curvature edges, addressing over-squashing and over-smoothing jointly

**Main findings**
- SOTA rewiring performance at a fraction of the compute
- AFRC distinguishes intra- from inter-community edges that plain Forman cannot

**Key takeaways**
- The triangle augmentation is what makes plain Forman curvature discriminative
- Linear-time cost makes it practical at scale
- Community-edge separation is a native property, useful beyond rewiring

**Relevance**
- The practical instrument for every curvature hypothesis - on 2,800 nodes / 3,900 edges AFRC is a few lines of networkx in milliseconds, so curvature-based duplicate and bridge detectors are cheap to threshold-sweep
- The triangle augmentation is exactly what separates dense duplicate clusters (high AFRC) from spurious single-bridge edges (low AFRC)

**Tags**
- #GraphCurvature #FormanRicci #Rewiring #GNN

**Source**
- Download: https://arxiv.org/pdf/2309.09384
- Local: [paper] afrc augmented forman-ricci curvature, 2023.pdf
