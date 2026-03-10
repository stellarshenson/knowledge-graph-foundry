"""FAISS-based exemplar index for embedding-based type candidate search."""

from __future__ import annotations

from loguru import logger
import numpy as np

from kg_builder_cli.types.ontology import TypeExemplar


class ExemplarIndex:
    """FAISS IndexFlatIP over L2-normalized exemplar embeddings.

    Provides cosine similarity search for type candidate ranking.
    """

    def __init__(self):
        self._index = None
        self._labels: list[str] = []  # type name per vector
        self._exemplar_names: list[str] = []  # entity name per vector

    @property
    def is_built(self) -> bool:
        return self._index is not None

    def build(
        self,
        type_exemplars: dict[str, tuple[TypeExemplar, ...]],
        embeddings: dict[str, list[float]],
    ) -> None:
        """Build FAISS index from exemplar embeddings.

        Args:
            type_exemplars: mapping from type name to exemplar tuples
            embeddings: mapping from exemplar name -> 1024-dim vector
        """
        import faiss

        vectors = []
        labels = []
        names = []

        for type_name, exemplars in type_exemplars.items():
            for exemplar in exemplars:
                emb = embeddings.get(exemplar.name)
                if emb is None:
                    continue
                vec = np.array(emb, dtype=np.float32)
                # L2-normalize for cosine similarity via inner product
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                vectors.append(vec)
                labels.append(type_name)
                names.append(exemplar.name)

        if not vectors:
            logger.warning("No exemplar embeddings available, index not built")
            return

        matrix = np.stack(vectors)
        dim = matrix.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(matrix)
        self._labels = labels
        self._exemplar_names = names

        logger.info(
            "ExemplarIndex built: {} vectors across {} types",
            len(vectors),
            len(type_exemplars),
        )

    def query(self, embedding: list[float], top_k: int = 3) -> list[tuple[str, float]]:
        """Return top-k (type_name, similarity) pairs for a query embedding.

        The embedding is L2-normalized before search. Similarities are cosine
        values in [0, 1] for normalized vectors.
        """
        if self._index is None:
            return []

        vec = np.array(embedding, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        k = min(top_k * 2, self._index.ntotal)  # search more to aggregate by type
        distances, indices = self._index.search(vec, k)

        # Aggregate by type - take max similarity per type
        type_scores: dict[str, float] = {}
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            type_name = self._labels[idx]
            score = float(dist)
            if type_name not in type_scores or score > type_scores[type_name]:
                type_scores[type_name] = score

        # Sort by similarity descending, return top-k types
        ranked = sorted(type_scores.items(), key=lambda x: -x[1])
        return ranked[:top_k]
