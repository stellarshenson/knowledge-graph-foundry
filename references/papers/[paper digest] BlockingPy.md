# BlockingPy

**Title**: BlockingPy - Approximate Nearest Neighbour blocking for scalable entity resolution (see arXiv for full title)
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2504.04266
**Publication date**: 2025-04 (first arXiv version)

## Core mechanism + measured results
- Formalizes using Approximate Nearest Neighbour (ANN) search as a blocking step for entity resolution / record linkage
- Blocking reduces the naive O(n^2) all-pairs comparison to a sub-quadratic candidate-generation architecture
- Records are embedded and ANN indexes retrieve only likely-match candidate pairs for expensive comparison
- Provides a Python library/implementation of the ANN-as-blocker approach
- Scales entity resolution to large record sets by capping candidate-pair volume
- Positions ANN blocking as a general, index-agnostic front end to any pairwise matcher

## Relevance to Knowledge Graph Foundry
Blueprint for scaling KGF's Bayesian entity resolution: use ANN blocking to generate candidate merge pairs sub-quadratically before running the expensive Bayesian posterior comparison, keeping resolution tractable as the graph grows.
