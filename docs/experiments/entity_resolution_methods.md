# Entity Resolution Methods - Experiment Results

This document captures the rationale and findings for the entity resolution approach implemented in v03.

## Problem Statement

Multi-doc benchmark v02 scored 76% hybrid with cross-document entity resolution at 17% (1/6 checks). The graph contained 30 humidifier entities instead of 1-5, 9 OSA entities, and 7 CPAP entities. Root cause: per-document extraction creates entities with different IDs and names that never merge. Resolution was Levenshtein-only at 0.85 threshold - too strict and purely syntactic.

## Approaches Evaluated

### 1. Name Normalization

Strip generic suffixes (system, device, unit, equipment, therapy, machine, apparatus, instrument, module, assembly) and articles before comparison. This collapses "humidifier system" and "humidifier" to the same normalized form.

**Impact**: Directly addresses the most common duplication pattern where the same concept gets different qualifiers in different documents. Applied both to ID generation (dedup.py) and resolution matching (resolution.py).

### 2. Embedding-Based Similarity

Generate 1024-dim vectors via Amazon Titan Text Embeddings v2 (`amazon.titan-embed-text-v2:0`). Input: `"{type}: {name} - {description[:200]}"`. Build cosine similarity matrix for pairwise comparison.

**Rationale**: Captures semantic similarity that Levenshtein misses - "obstructive sleep apnea" vs "OSA" have zero string similarity but high semantic similarity when description context is included.

### 3. Graph-Based Community Detection

Considered spectral clustering (Laplacian eigendecomposition) vs simple connected components on thresholded similarity graph.

**Decision**: Connected components via Union-Find is sufficient and simpler. Spectral clustering adds complexity without clear benefit when the similarity signals (name + embedding) are already well-calibrated. The O(n^2) pairwise comparison within type blocks is acceptable for entity counts under 2000.

### 4. Multi-Signal Fusion

Combined approach: when embeddings available, require BOTH name similarity >= 0.65 AND cosine similarity >= 0.80 to merge. This prevents false positives from either signal alone.

**Fallback**: When embeddings unavailable, use normalized-name Levenshtein at original threshold (0.85).

## Implementation

- `normalization.py`: Shared name normalization (lowercase, strip suffixes, remove articles)
- `embeddings.py`: Titan v2 embedding generation via Bedrock
- `resolution.py`: Multi-signal matching with Union-Find connected components
- `dedup.py`: Uses normalized names for deterministic ID hashing

## Key Thresholds

| Signal | Threshold | Rationale |
|---|---|---|
| Levenshtein (no embeddings) | 0.85 | Backward-compatible, catches spelling variants |
| Levenshtein (with embeddings) | 0.65 | Relaxed because embeddings provide second signal |
| Cosine similarity | 0.80 | High enough to avoid cross-concept merges |
