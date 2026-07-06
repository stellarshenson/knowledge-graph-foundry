"""R4 ANN blocking: FAISS-backed synonym candidate generation.

Within each type block, entities carrying an embedding are compared. Small
blocks (below `min_entities`) use exact brute-force all-pairs cosine, which is
parity with the original resolver. Large blocks build a FAISS `IndexFlatIP`
over L2-normalized vectors and keep the `top_k` nearest neighbours per entity
above the threshold. `IndexFlatIP` is an exact inner-product search, so the
result is deterministic and matches the brute-force path on the same block.
"""

from __future__ import annotations

from collections import defaultdict

from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.resolution.similarity import cosine_similarity


def _brute_force(
    entities: list[Entity], members: list[int], threshold: float
) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for pos, i in enumerate(members):
        for j in members[pos + 1 :]:
            if cosine_similarity(entities[i].embedding, entities[j].embedding) >= threshold:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def _ann_block(
    entities: list[Entity], members: list[int], top_k: int, threshold: float
) -> set[tuple[int, int]]:
    import faiss
    import numpy as np

    vectors = np.asarray([entities[i].embedding for i in members], dtype="float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    k = min(top_k + 1, len(members))  # +1: the query returns itself first
    scores, neighbours = index.search(vectors, k)
    pairs: set[tuple[int, int]] = set()
    for row, i in enumerate(members):
        for col in range(k):
            n = int(neighbours[row][col])
            if n < 0 or n == row:
                continue
            if scores[row][col] >= threshold:
                j = members[n]
                pairs.add((min(i, j), max(i, j)))
    return pairs


def ann_candidates(
    entities: list[Entity],
    top_k: int,
    min_entities: int,
    threshold: float = 0.82,
) -> set[tuple[int, int]]:
    """Within-type embedding candidate pairs above `threshold`.

    Blocks with at least `min_entities` embedded members use FAISS ANN; smaller
    blocks fall back to brute-force all-pairs cosine. Entities without an
    embedding are skipped. Returns index pairs `(min, max)`.
    """
    blocks: dict[str, list[int]] = defaultdict(list)
    for idx, entity in enumerate(entities):
        if entity.embedding:
            for t in entity.types:
                blocks[t].append(idx)

    pairs: set[tuple[int, int]] = set()
    for members in blocks.values():
        if len(members) >= min_entities:
            pairs |= _ann_block(entities, members, top_k, threshold)
        else:
            pairs |= _brute_force(entities, members, threshold)
    return pairs
