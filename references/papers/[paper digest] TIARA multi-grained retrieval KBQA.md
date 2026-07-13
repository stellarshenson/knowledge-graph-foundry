**TIARA: Multi-grained Retrieval for Robust Question Answering over Large Knowledge Bases (2022)**

Pre-trained language models generating logical forms for KBQA face two coupled problems: they must ground the question in a KB with tens of millions of entities and thousands of schema items, and they must generate output that is both semantically correct and syntactically executable - hard when the KB is too large to fit in context and the i.i.d. training/test assumption breaks down for unseen compositions or entirely unseen domains. TIARA's shift is to retrieve at three separate granularities before generation - entities, exemplary logical forms, and schema items (classes/relations) independently - rather than retrieving only entity-neighborhood context, and to constrain the PLM's output space at decode time with prefix tries built from the KB schema. TIARA beats the prior SOTA by **at least 4.1 F1 points on GrailQA and 1.1 F1 points on WebQSP**, with the largest gain concentrated in the hardest setting: **4.7 F1 points on GrailQA's zero-shot generalization split**.

**Key mechanism**
- Three independent retrievers feed one T5 generator: (1) entity retrieval via span-classification mention detection + FACC1 candidate generation + cross-encoder disambiguation; (2) exemplary logical form retrieval - enumerates candidate s-expressions up to two hops from linked entities, ranked by a BERT cross-encoder; (3) schema retrieval - a separate cross-encoder scoring (question, class-or-relation) pairs *independent of entity linking*, surfacing relevant schema items beyond the 2-hop enumeration radius
- Schema retrieval is the answer to "logical-form enumeration alone can't handle >2-hop or diverse function types": having no anchor-entity requirement, it acts as a semantic supplement independent of graph connectivity
- Constrained decoding: prefix tries built over the KB's valid class/relation vocabularies restrict the T5 decoder to syntactically valid, KB-existing schema items at each generation step
- The T5 input concatenates the question with all three retrieved context types, letting the PLM attend jointly to semantic and syntactic references
- Evaluated on three generalization splits (I.I.D., compositional, zero-shot) to test whether retrieval helps beyond memorized training distributions

**Main findings**
- GrailQA hidden test set: **73.0 EM / 78.5 F1 overall** (87.8/90.6 I.I.D., 69.2/76.5 compositional, 68.0/73.9 zero-shot) - beats RnG-KBQA across every category, largest margin (**4.7 F1 points**) in zero-shot
- WebQSP (non-oracle entity linking): **76.7 F1 / 73.9 Hits@1**, ahead of Program Transfer (76.5/74.6) in F1 without assuming a fixed hop count; with oracle linking, F1 rises to **78.9**
- Removing exemplary logical form retrieval (ELF) is catastrophic in zero-shot: **F1 drops from 80.7 to 54.2** - without ELF examples the PLM has no syntactic template for unseen compositions
- Removing schema retrieval costs **2.7 F1 points overall**, concentrated where ELF enumeration fails to reach the target (>2 hops or unusual functions)
- Removing constrained decoding costs a modest **0.4 F1 points overall** - most of the gain is retrieval quality, not decode-time constraint
- Removing ELF, schema, and constrained decoding together collapses zero-shot F1 to **2.3 points** (from 80.7) - the three mechanisms are strongly complementary, not redundant

**Key takeaways**
- Retrieving multiple *independent* granularities lets each mechanism cover the other's blind spot - ELF supplies syntactic templates but is hop-bounded; schema retrieval has no hop bound but weaker syntactic guidance; the combination drives zero-shot robustness
- Zero-shot/OOD generalization is where retrieval augmentation earns its keep - ablations show the largest F1 collapses under zero-shot, much smaller under I.I.D.
- Constrained decoding is a comparatively cheap gain, useful for syntactic validity but not a substitute for retrieval quality

**Relevance**
- TIARA's schema-retrieval channel (connectivity-independent question-to-relation/class match) is a close analogue to R50's GLiNER entity-type + question-TYPE label axis (H581/H586); its finding that schema retrieval is *complementary* rather than *redundant* to path retrieval is a useful prior for how R50 should expect typed signals to combine with, not replace, the existing dense+PPR seed mechanism
- Caveat: TIARA assumes a well-defined KB schema (2K classes, 6K relations) enumerable for prefix-trie construction; KGF's self-extracted, higher-entropy relation vocabulary (H395) would make the constrained-decoding half hard to reproduce as-is, though the independent schema-channel idea does not require it

**Tags**
- #KBQA
- #MultiGrainedRetrieval
- #ZeroShotGeneralization
- #ConstrainedDecoding
- #SemanticParsing

**Source**
- Download: https://arxiv.org/abs/2210.12925
- Local: [paper] TIARA multi-grained retrieval KBQA, 2022.pdf
