**Semantic Parsing with Candidate Expressions for Knowledge Base Question Answering (2024)**

Type-constrained decoding keeps a seq2seq semantic parser's output well-typed but ignores the actual content of the KB - the grammar knows a slot must hold a "relation" but not which relations exist. This paper augments the decoding grammar with candidate expressions: at each generation step, the action space is restricted to KB elements (entities, relations, attribute values) that are actually valid at that position, discovered via trie-based lookup rather than free generation. Combined with two speed optimizations (sub-type inference and mask caching), the resulting parser sets **state-of-the-art accuracy on both KQAPRO and OVERNIGHT** while adding negligible decoding overhead - the type+candidate-expression variant nearly matches type-only decoding speed despite far tighter constraints.

**Key mechanism**
- Grammar defines actions as typed production rules; a node class c (e.g., `keyword-relation`) has an associated candidate-expression set E(c;k) drawn from the actual KB k, so decoding at that node is restricted to a trie of valid KB elements rather than the full vocabulary
- Multiple trie data structures index the candidate-expression sets per node class, enabling fast prefix-constrained lookup during beam search
- Sub-type inference collapses redundant intermediate non-terminals (e.g. `<RESULT>` directly to `<RESULT-REL-Q-VALUE>`), shortening the action sequence and thus directly cutting decode time since cost is proportional to sequence length
- Union types let a single left-hand-side symbol carry multiple types simultaneously, avoiding grammar duplication for KB elements with more than one semantic role
- Mask caching stores previously computed decoding masks (which actions are legal at a given partial parse state) so repeated partial-state lookups skip recomputation - the dominant cost driver at larger beam/batch sizes
- Applies uniformly to both strong supervision (gold logical forms) and weak supervision (denotation-only) training regimes

**Main findings**
- KQAPRO (large-scale KB benchmark): full grammar (ΨHYBR, types + candidate expressions) reaches **93.19% overall accuracy** with beam size 1, rising to **93.34%** at beam size 4, ahead of type-only decoding (92.56%) and no-constraint decoding (92.52%)
- OVERNIGHT (multi-domain benchmark): ΨHYBR reaches **83.8%** overall test accuracy vs 82.4% for unconstrained decoding and 83.5% for type-only, with the largest per-domain gain on Blocks (66.9% unconstrained -> **68.2%** with type/candidate-expression constraints)
- Decoding speed at batch=64, beam=4 on KQAPRO: full constraints (ΨHYBR) with both speed optimizations reach **52.75ms** per sequence vs **95.49ms** with mask caching disabled and **105.21ms** with both optimizations disabled - roughly a **2x** speedup from the two techniques combined
- All variants with candidate-expression constraints beat prior published semantic parsers (BART-KoPL, GraphQ-IR, Semantic Anchor) on both benchmarks under strong supervision, and the accuracy gain persists under weak (denotation-only) supervision as well
- Sub-type inference's sequence-shortening effect and mask caching's lookup-avoidance effect are complementary - each contributes independently to the roughly 2x speed recovery that closes the gap opened by adding candidate-expression constraints

**Key takeaways**
- Constraining generation to KB-grounded candidate sets (not just types) is a strict accuracy improvement over type-only constrained decoding, and the added constraint checking can be made nearly free with trie indexing plus caching - accuracy and speed are not in tension here
- The pattern generalizes beyond semantic parsing: any generation task where the output must reference a large, structured, known vocabulary (KB elements, schema fields, valid graph paths) can adopt trie-constrained candidate-expression decoding to eliminate hallucinated references by construction
- Sub-type inference (collapsing the grammar to the shortest correct derivation) is a free win that should be applied regardless of whether candidate-expression constraints are used at all

**Relevance**
- Bears directly on R50's typed/topology retrieval design: trie-constrained decoding over KGF's actual graph schema and existing entity/relation vocabulary could eliminate a class of retrieval-time hallucinated relation or entity references at near-zero latency cost, if KGF ever needs a generative query-construction step rather than pure graph traversal
- The mask-caching pattern (cache legal-action masks keyed on partial decode state) is reusable wherever KGF performs constrained enumeration over its own schema (e.g., candidate subgraph generation)

**Tags**
- #KBQA
- #ConstrainedDecoding
- #SemanticParsing
- #TrieIndexing

**Source**
- Download: https://arxiv.org/abs/2410.00414
- Local: [paper] candidate expressions KBQA, 2024.pdf
