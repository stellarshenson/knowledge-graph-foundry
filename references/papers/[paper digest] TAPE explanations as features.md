**Harnessing Explanations: LLM-to-LM Interpreter for Enhanced Text-Attributed Graph Representation Learning (TAPE), He, Bresson, Laurent, Perold, LeCun, Hooi (NUS / LMU / Meta AI / NYU), ICLR 2024 (arXiv 2305.19523)**

The clean test of ENRICHING node text with LLM-generated explanations and feeding it to the retrieval/representation model - the text-side-vs-embedding-side question for family 3. Each node's raw text is augmented with an LLM's zero-shot prediction plus its free-text EXPLANATION; a smaller LM ("interpreter") encodes the enriched text into node features for a downstream GNN.

**Key mechanism**
- Prompt an LLM per node: predict a label AND explain its reasoning in text (the explanation is the enrichment - new, model-generated text attached to the node)
- Fine-tune a small LM to encode {original text + prediction + explanation} into features (LLM-to-LM interpreter)
- Downstream GNN consumes the enriched features - the enrichment lives in TEXT space, then gets embedded, rather than being an embedding-space operation

**Main findings**
- SOTA on Cora, PubMed, ogbn-arxiv and a new tape-arxiv23 dataset - LLM-explanation text as node features beats shallow (bag-of-words/skip-gram) and plain-LM node features
- 2.88x faster training than the closest LM-augmented baseline on ogbn-arxiv - enrichment is done once at ingest, not per query
- The GAIN is the generated explanation text, not just the label: explanations add discriminative textual signal the raw node text lacked

**Relevance to KGF**
- Answers the family-3 core question - does text-side enrichment beat embedding-side? TAPE shows text-space enrichment (generate explanation -> re-embed) is a strong, ingest-once lever; combined with H627 (confirmed embedding-space smoothing) it argues the two channels are COMPLEMENTARY, not substitutes - text enrichment feeds better vectors, smoothing spreads them
- Direct mechanism for starved self-extracted nodes: generate an explanation/description from context and re-embed - the enriched vector is what dense retrieval sees; this is the honest "where does the text come from" answer alongside KELM's neighbourhood verbalization (KELM = triples->text; TAPE = LLM-reasoning->text)
- Ingest-once cost profile matches doc2query/QuOTE - no per-query LLM call
- Ceiling PRICED by R57-H648: if entity features (description length/degree) do not separate hit/miss carriers, enrichment cannot help surfaceability; TAPE-style enrichment is only worth its LLM cost if H648 confirms the starvation signal (AUC >= 0.65)

**Tags**: #TAPE #NodeTextEnrichment #Explanations #TextVsEmbedding #EntityStrengthening #AmplificationFamily3

**Source**: https://arxiv.org/abs/2305.19523. Local: [paper] TAPE explanations as features, 2023.pdf
