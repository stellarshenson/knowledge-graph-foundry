**Hubs in Space: Popular Nearest Neighbors in High-Dimensional Data, Radovanovic, Nanopoulos, Ivanovic, JMLR 2010**

The canonical account of HUBNESS - the pathology where a few points become nearest neighbors of a large fraction of ALL points: as intrinsic dimensionality grows, the distribution of k-occurrences N_k (how often a point appears in others' k-NN lists) becomes **increasingly right-skewed**, creating hubs (huge N_k) and anti-hubs/orphans (N_k ~ 0). An inherent property of high-dimensional data, distinct from but related to distance concentration.

**Key mechanism**
- Points closer to the data-distribution mean (or their cluster center) are, in high dimension, systematically closer to ALL other points → they enter disproportionately many kNN lists; the effect strengthens with INTRINSIC (not embedding) dimensionality
- Skewness S_{N_k} of the N_k distribution is the standard hubness measure; grows with dimension across all tested distance families (Euclidean, cosine-class, Manhattan, Canberra)
- Dimensionality reduction below the intrinsic dimension reduces hubness; above it, little effect

**Main findings**
- Hubness degrades kNN-based tasks: hubs dominate retrieval lists regardless of query semantics ("popular nearest neighbors" match everything); anti-hubs become unretrievable
- Bad hubs (hubs whose label mismatches their neighbors) carry outsized error influence in classification/retrieval
- Real data behaves by INTRINSIC dimensionality: adding points to a fixed space (growing N) sharpens hub identities - occurrence counts concentrate

**Key takeaways**
- The embedding-side mechanism candidate for REG-1: as the 2wiki pile grows, thematically uniform passages (films, directors, dates of one schema) crowd the embedding region; centrally-located generic entities become hubs of the vector index and crowd out specific gold carriers (directors) from top-k lists - retrieval degrades with corpus SIZE at fixed k with no graph pathology at all
- Instrument: per-checkpoint N_k skewness of the entity/passage vector index + hub identity churn; a skewness jump or a new hub capturing the film-question region localizes the shift
- The "F-family heretic" grounding: if N_k skewness moves at doc 135-154 and graph metrics do not, the regression is an index-geometry problem and the graph is innocent

**Tags**: #Hubness #kNN #HighDimensional #VectorRetrieval #EmbeddingCrowding

**Source**: https://jmlr.org/papers/volume11/radovanovic10a/radovanovic10a.pdf. Local: [paper] Hubs in Space kNN Hubness, 2010-09.pdf
