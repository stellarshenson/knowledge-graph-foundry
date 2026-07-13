**Language Recognition using Random Indexing, Joshi, Halseth, Kanerva (UC Berkeley), 2014-12**

On 21,000 short sentences spanning 21 languages (Europarl Parallel Corpus, 1,000 sentences per language), a 10,000-dimensional Random Indexing hypervector built from letter tetragrams (n=4) identifies the correct language with 97.8% accuracy - a fully deterministic, single-pass, training-free encoding that needs about 1 second per language to build and processes text at roughly 100,000 letters/second on a laptop.

**Key mechanism**
- MAP coding (Multiply, Add, Permute): each of the 26 letters plus Space gets a fixed D-dimensional (D=10,000) Random Label - a random vector with an equal number of +1s and -1s, nearly orthogonal to every other Random Label with high probability
- n-Gram Vector: an n-letter block is encoded by repeatedly applying a fixed random permutation ρ to each letter's Random Label by its position, then multiplying (elementwise) the results together - e.g. block "grab" -> ρρρG * ρρR * ρA * B; permutation makes the encoding order-sensitive (A-B-C != A-C-B)
- Text Vector: bundle (elementwise sum) of the n-Gram Vectors for every sliding-window block in the text - a single fixed-width vector standing in for the whole letter-sequence distribution
- Language Vector: bundle of Text Vectors from many samples of a known language; classification is nearest-cosine between an unknown Text Vector and each Language Vector
- Incremental sliding window: because a vector is its own multiplicative inverse (A*A=1), the n-Gram Vector for the next block is obtained by removing the oldest letter's contribution and multiplying in the new one, giving O(D) per-block update and O(D*m) total for a text of length m - no need to recompute from scratch

**Main findings**
- Detection accuracy by n-gram size on the Europarl test set: n=1 (letter histogram) 74.9%, n=2 94.0%, n=3 97.3%, n=4 97.8%, n=5 97.3% - tetragrams are the sweet spot, larger blocks do not help further
- Language Vectors were trained from about 100,000 bytes of text per language (Project Gutenberg and Wortschatz Corpora), covering 23 languages for the vector-space clustering demo and 21 for the detection benchmark
- The confusion matrix (Table 2, trigram vectors) shows most residual errors fall inside language families - e.g. Slovak sentences were misread as Czech 68/1000 times and as Slovenian 14/1000; Latvian and Lithuanian cross-confuse at 15-19/1000
- A t-SNE projection of the 10,000-dimensional Language Vectors (trigram-based) roughly reproduces known language-family relationships without any explicit family labels supplied to the method
- Whole pipeline is a single pass over the data with no iterative training and no gradient computation

**Key takeaways**
- Directly the mechanism for R47-H503 span-string-to-signature encoding: bind sliding-window letter n-grams (permute + multiply) and bundle them (sum) into one fixed-D hypervector, then compare candidate spans by cosine similarity - deterministic, no LLM call, no training pass, reproducible byte-for-byte
- Cost profile matches ingest-time-not-query-time doctrine: O(D*m) single pass per span/text, and the incremental sliding-window update means re-scoring a shifted window costs O(D) rather than a full recompute
- Deterministic by construction (same text always yields the same vector) is a good property for a benchmark-first, reproducible foundry pipeline - no stochastic training to seed or drift
- Ceiling effect on block size (n=4 beats n=5) is a caution against assuming more context always helps a hypervector signature; the right window size should be swept, not maximized
- Caveat for KGF's use case: validated only on clean, single-sentence, multi-lingual text for language identification, not on near-duplicate entity-span discrimination within a single language/domain - the closer analogy to a span-string signature for entity resolution remains to be checked empirically

**Tags**: #RandomIndexing #Hyperdimensional #MAPCoding #LanguageID #Bundling #Binding

**Source**: https://arxiv.org/abs/1412.7026. Local: [paper] Random Indexing Language Geometry, 2014.pdf
