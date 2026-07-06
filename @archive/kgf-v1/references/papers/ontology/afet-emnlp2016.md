# AFET: Automatic Fine-Grained Entity Typing by Hierarchical Partial-Label Embedding

- **Authors**: Xiang Ren, Wenqi He, Meng Qu, Lifu Huang, Heng Ji, Jiawei Han
- **Venue**: EMNLP 2016 (Conference on Empirical Methods in Natural Language Processing)
- **URL**: https://aclanthology.org/D16-1144/
- **Key contribution**: Hierarchical partial-label embedding for fine-grained entity typing. Addresses the problem of noisy type labels in knowledge bases by modeling type hierarchy as a constraint during embedding. Entities can have multiple valid types at different hierarchy levels, and the model learns to separate clean from noisy labels using the hierarchy structure.
- **Relevance to H5g**: Foundation for multi-facet entity labels. When an entity legitimately belongs to types under different hierarchy parents (e.g., Feature and Component), both labels are preserved rather than forced into a single type. The partial-label approach validates that entities can carry multiple type assignments without contradiction.
