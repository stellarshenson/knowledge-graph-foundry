"""Multi-channel type metrics for prior computation.

Computes 19 per-type metrics across 6 categories: frequency-derived,
distribution shape, embedding space, graph topology, temporal/accumulation,
and cross-run calibration.
"""

from __future__ import annotations

from collections import Counter
import math

from loguru import logger

from knowledge_graph_foundry.types.extraction import ExtractionResult

_NAN = float("nan")


class TypeMetricsCollector:
    """Compute 19 per-type metrics from accumulated extraction results."""

    def __init__(
        self,
        results: list[ExtractionResult],
        frequencies: dict[str, int],
        type_exemplars: dict | None = None,
        cross_type_stats: dict | None = None,
        calibration_data: dict | None = None,
        prev_frequencies: dict[str, int] | None = None,
    ):
        self._results = results
        self._frequencies = frequencies
        self._type_exemplars = type_exemplars or {}
        self._cross_type_stats = cross_type_stats or {}
        self._calibration_data = calibration_data or {}
        self._prev_frequencies = prev_frequencies or {}
        self._all_entities = []
        self._per_doc_entities: list[list] = []
        for r in results:
            self._all_entities.extend(r.entities)
            self._per_doc_entities.append(r.entities)

    def compute(self) -> dict[str, dict[str, float]]:
        """Compute all 19 metrics for all types. Returns {type_name: {metric: value}}."""
        types = list(self._frequencies.keys())
        if not types:
            return {}

        metrics: dict[str, dict[str, float]] = {}
        for t in types:
            metrics[t] = {}

        # Frequency-derived (F1-F3)
        self._compute_frequency_metrics(metrics, types)
        # Distribution shape (D1-D3)
        self._compute_distribution_metrics(metrics, types)
        # Embedding space (E1-E4)
        self._compute_embedding_metrics(metrics, types)
        # Graph topology (G1-G3)
        self._compute_topology_metrics(metrics, types)
        # Temporal / accumulation (T1-T3)
        self._compute_temporal_metrics(metrics, types)
        # Cross-run calibration (C1-C3)
        self._compute_calibration_metrics(metrics, types)

        logger.info("type metrics computed: {} types, 19 metrics each", len(types))
        return metrics

    def _compute_frequency_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """F1: freq_log_smooth, F2: freq_rank_pct, F3: freq_cv."""
        total = sum(self._frequencies.values())
        k = len(types)
        log_total_k = math.log(total + k) if (total + k) > 0 else 1.0

        # F1: log-smoothed frequency
        for t in types:
            freq = self._frequencies.get(t, 0)
            metrics[t]["freq_log_smooth"] = math.log(freq + 1) / log_total_k

        # F2: rank percentile (0.0 = most frequent)
        sorted_types = sorted(types, key=lambda t: self._frequencies.get(t, 0), reverse=True)
        n = len(sorted_types)
        for rank, t in enumerate(sorted_types):
            metrics[t]["freq_rank_pct"] = rank / max(n - 1, 1)

        # F3: coefficient of variation across documents
        for t in types:
            per_doc_freqs = []
            for doc_entities in self._per_doc_entities:
                count = sum(1 for e in doc_entities if e.type == t)
                per_doc_freqs.append(count)
            if per_doc_freqs and len(per_doc_freqs) > 1:
                mean_f = sum(per_doc_freqs) / len(per_doc_freqs)
                if mean_f > 0:
                    var = sum((x - mean_f) ** 2 for x in per_doc_freqs) / len(per_doc_freqs)
                    metrics[t]["freq_cv"] = math.sqrt(var) / mean_f
                else:
                    metrics[t]["freq_cv"] = 0.0
            else:
                metrics[t]["freq_cv"] = 0.0

    def _compute_distribution_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """D1: desc_entropy, D2: name_diversity, D3: top3_concentration."""
        from knowledge_graph_foundry.extraction.normalization import normalize_entity_name

        for t in types:
            type_entities = [e for e in self._all_entities if e.type == t]
            if not type_entities:
                metrics[t]["desc_entropy"] = 0.0
                metrics[t]["name_diversity"] = 0.0
                metrics[t]["top3_concentration"] = 1.0
                continue

            # D1: Shannon entropy of word frequencies across descriptions
            word_counts: Counter = Counter()
            for e in type_entities:
                if e.description:
                    for word in e.description.lower().split():
                        if len(word) > 2:
                            word_counts[word] += 1
            total_words = sum(word_counts.values())
            if total_words > 0:
                entropy = 0.0
                for count in word_counts.values():
                    p = count / total_words
                    if p > 0:
                        entropy -= p * math.log2(p)
                metrics[t]["desc_entropy"] = entropy
            else:
                metrics[t]["desc_entropy"] = 0.0

            # D2: name diversity
            unique_names = {normalize_entity_name(e.name) for e in type_entities}
            metrics[t]["name_diversity"] = len(unique_names) / len(type_entities)

            # D3: top-3 concentration
            name_freqs = Counter(normalize_entity_name(e.name) for e in type_entities)
            top3 = sum(f for _, f in name_freqs.most_common(3))
            total = sum(name_freqs.values())
            metrics[t]["top3_concentration"] = top3 / total if total > 0 else 1.0

    def _compute_embedding_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """E1: emb_cohesion, E2: emb_separation, E3: emb_silhouette, E4: emb_centroid_dist."""
        import numpy as np

        # Group embeddings by type
        type_embeddings: dict[str, list[list[float]]] = {}
        for e in self._all_entities:
            if e.embedding:
                type_embeddings.setdefault(e.type, []).append(e.embedding)

        # Compute centroids
        centroids: dict[str, list[float]] = {}
        for t, embs in type_embeddings.items():
            arr = np.array(embs)
            centroids[t] = arr.mean(axis=0).tolist()

        for t in types:
            embs = type_embeddings.get(t)
            if not embs or len(embs) < 2:
                metrics[t]["emb_cohesion"] = _NAN
                metrics[t]["emb_separation"] = _NAN
                metrics[t]["emb_silhouette"] = _NAN
                metrics[t]["emb_centroid_dist"] = _NAN
                continue

            arr = np.array(embs)
            centroid = np.array(centroids[t])

            # E1: mean pairwise cosine similarity within type
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            normalized = arr / norms
            sim_matrix = normalized @ normalized.T
            n = len(embs)
            # Mean of upper triangle (excluding diagonal)
            triu_indices = np.triu_indices(n, k=1)
            metrics[t]["emb_cohesion"] = float(sim_matrix[triu_indices].mean())

            # E4: mean entity-to-own-centroid distance
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm > 0:
                centroid_normalized = centroid / centroid_norm
                dists = 1.0 - (normalized @ centroid_normalized)
                metrics[t]["emb_centroid_dist"] = float(dists.mean())
            else:
                metrics[t]["emb_centroid_dist"] = _NAN

            # E2: cosine distance to nearest other type centroid
            min_dist = float("inf")
            for other_t, other_centroid in centroids.items():
                if other_t == t:
                    continue
                c1 = np.array(centroids[t])
                c2 = np.array(other_centroid)
                n1, n2 = np.linalg.norm(c1), np.linalg.norm(c2)
                if n1 > 0 and n2 > 0:
                    dist = 1.0 - float(np.dot(c1, c2) / (n1 * n2))
                    if dist < min_dist:
                        min_dist = dist
            metrics[t]["emb_separation"] = min_dist if min_dist != float("inf") else _NAN

            # E3: silhouette score per entity averaged
            sil_scores = []
            for i, emb in enumerate(arr):
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    continue
                emb_normalized = emb / emb_norm

                # a = mean distance to own cluster
                a = 1.0 - float(
                    np.mean(
                        [float(np.dot(emb_normalized, normalized[j])) for j in range(n) if j != i]
                    )
                )

                # b = min mean distance to other clusters
                b = float("inf")
                for other_t, other_embs in type_embeddings.items():
                    if other_t == t or not other_embs:
                        continue
                    other_arr = np.array(other_embs)
                    other_norms = np.linalg.norm(other_arr, axis=1, keepdims=True)
                    other_norms = np.where(other_norms == 0, 1.0, other_norms)
                    other_normalized = other_arr / other_norms
                    mean_dist = 1.0 - float((other_normalized @ emb_normalized).mean())
                    if mean_dist < b:
                        b = mean_dist

                if b != float("inf"):
                    sil = (b - a) / max(a, b) if max(a, b) > 0 else 0.0
                    sil_scores.append(sil)

            metrics[t]["emb_silhouette"] = float(np.mean(sil_scores)) if sil_scores else _NAN

    def _compute_topology_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """G1: rel_type_diversity, G2: type_cooccurrence, G3: rel_reciprocity."""
        # Collect all relationships
        all_rels = []
        for r in self._results:
            all_rels.extend(r.relationships)

        # Build entity -> type map
        entity_type_map: dict[str, str] = {}
        for e in self._all_entities:
            entity_type_map[e.id] = e.type

        for t in types:
            # G1: distinct relationship types involving this type
            rel_types_set: set[str] = set()
            incoming = 0
            outgoing = 0
            for rel in all_rels:
                src_type = entity_type_map.get(rel.source)
                tgt_type = entity_type_map.get(rel.target)
                if src_type == t or tgt_type == t:
                    rel_types_set.add(rel.type)
                    if src_type == t:
                        outgoing += 1
                    if tgt_type == t:
                        incoming += 1
            metrics[t]["rel_type_diversity"] = float(len(rel_types_set))

            # G3: reciprocity - fraction of rels with reverse edge
            if outgoing + incoming > 0:
                # Count bidirectional pairs
                edge_set = set()
                for rel in all_rels:
                    src_type = entity_type_map.get(rel.source)
                    tgt_type = entity_type_map.get(rel.target)
                    if src_type == t or tgt_type == t:
                        edge_set.add((rel.source, rel.target, rel.type))
                reciprocal = 0
                for src, tgt, rtype in edge_set:
                    if (tgt, src, rtype) in edge_set:
                        reciprocal += 1
                total_edges = len(edge_set)
                metrics[t]["rel_reciprocity"] = (
                    reciprocal / total_edges if total_edges > 0 else 0.0
                )
            else:
                metrics[t]["rel_reciprocity"] = 0.0

        # G2: type co-occurrence (Jaccard across documents)
        doc_type_sets: list[set[str]] = []
        for doc_entities in self._per_doc_entities:
            doc_type_sets.append({e.type for e in doc_entities})

        for t in types:
            jaccards = []
            for other_t in types:
                if other_t == t:
                    continue
                both = sum(1 for ds in doc_type_sets if t in ds and other_t in ds)
                either = sum(1 for ds in doc_type_sets if t in ds or other_t in ds)
                if either > 0:
                    jaccards.append(both / either)
            metrics[t]["type_cooccurrence"] = sum(jaccards) / len(jaccards) if jaccards else 0.0

    def _compute_temporal_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """T1: discovery_order, T2: tar_at_discovery, T3: cross_type_rate."""
        total_docs = len(self._per_doc_entities)

        # Track first appearance of each type
        first_appearance: dict[str, int] = {}
        types_seen: set[str] = set()
        type_accumulation: list[int] = []
        for doc_idx, doc_entities in enumerate(self._per_doc_entities):
            doc_types = {e.type for e in doc_entities}
            for t in doc_types:
                if t not in first_appearance:
                    first_appearance[t] = doc_idx
            types_seen.update(doc_types)
            type_accumulation.append(len(types_seen))

        for t in types:
            # T1: discovery order (0 = discovered first)
            first_doc = first_appearance.get(t, total_docs - 1)
            metrics[t]["discovery_order"] = first_doc / max(total_docs - 1, 1)

            # T2: type accumulation rate when first discovered
            if first_doc < len(type_accumulation) and first_doc > 0:
                tar = type_accumulation[first_doc] / (first_doc + 1)
            else:
                tar = 1.0
            metrics[t]["tar_at_discovery"] = tar

            # T3: cross-type rate
            type_entities = [e for e in self._all_entities if e.type == t]
            total_type = len(type_entities)
            if total_type > 0 and self._cross_type_stats:
                cross_count = sum(
                    1
                    for s in self._cross_type_stats
                    if isinstance(s, dict) and (s.get("type_a") == t or s.get("type_b") == t)
                )
                metrics[t]["cross_type_rate"] = cross_count / total_type
            else:
                metrics[t]["cross_type_rate"] = 0.0

    def _compute_calibration_metrics(
        self, metrics: dict[str, dict[str, float]], types: list[str]
    ) -> None:
        """C1: hist_mean_posterior, C2: hist_remap_rate, C3: cross_run_freq_delta."""
        for t in types:
            cal = self._calibration_data.get(t)
            if cal:
                metrics[t]["hist_mean_posterior"] = cal.get("mean_posterior", _NAN)
                obs = cal.get("observation_count", 0)
                remap = cal.get("remap_count", 0)
                metrics[t]["hist_remap_rate"] = remap / obs if obs > 0 else _NAN
            else:
                metrics[t]["hist_mean_posterior"] = _NAN
                metrics[t]["hist_remap_rate"] = _NAN

            # C3: cross-run frequency delta
            prev = self._prev_frequencies.get(t, 0)
            curr = self._frequencies.get(t, 0)
            if prev > 0:
                metrics[t]["cross_run_freq_delta"] = abs(curr - prev) / prev
            else:
                metrics[t]["cross_run_freq_delta"] = _NAN
