**A Survey on Graph Structure Learning: Progress and Opportunities (2021)**

This survey covers methods that jointly learn graph structure and representations when the given structure is noisy or incomplete. It organizes the field into a taxonomy of how the adjacency is produced and optimizes it jointly with the task loss under structural regularizers. The transferable idea for a discrete KG is the task-loss gradient over the adjacency as an edit-proposal ranker.

**Key mechanism**
- Taxonomy: metric-based (edge weights from feature similarity), neural (networks emit edge probabilities), direct/parameterized (adjacency as a free learnable parameter)
- Adjacency optimized jointly with task loss under sparsity/smoothness/low-rank/connectivity regularizers
- Anchors: LDS learns Bernoulli edge distributions via bilevel optimization (memory-bound at ~19k-node Pubmed); IDGL iteratively refines from cosine similarity with top-k thresholding; SLAPS adds self-supervised denoising

**Main findings**
- A unified taxonomy of structure-learning approaches
- Regularizer catalog: sparsity, smoothness, low-rank, connectivity
- LDS is memory-bound at ~19k-node Pubmed

**Key takeaways**
- The adjacency can be treated as a parameter under a task loss
- Dense relaxation is memory-feasible at a few thousand nodes
- Regularizers translate into penalty terms for a foundry potential

**Relevance**
- The literal "graph as a parameter with a task loss and gradients" domain
- For a discrete human-auditable KG the transferable piece is the gradient dL_task/dA_ij as an edit-proposal RANKER, not a soft-edge store; the regularizer catalog informs penalty terms in a foundry potential
- Dense relaxation at 2,800 nodes (~7.8M entries) is memory-feasible

**Tags**
- #GraphStructureLearning #GNN #Survey

**Source**
- Download: https://arxiv.org/pdf/2103.03036
- Local: [paper] graph structure learning survey, 2021.pdf
