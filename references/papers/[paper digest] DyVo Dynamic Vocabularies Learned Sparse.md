# DyVo: Dynamic Vocabularies for Learned Sparse Retrieval with Entities

**Authors**: Thong Nguyen, Shubham Chatterjee, Sean MacAvaney, Iain Mackie, Jeff Dalton, Andrew Yates (Amsterdam, Edinburgh, Glasgow)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2410.07722

**Publication date**: 2024-10-15 (arXiv v2, per PDF footer; arXiv:2410.07722)

## Summary

- Diagnoses a specific failure of Learned Sparse Retrieval (LSR, e.g. SPLADE): BPE/wordpiece tokenizers shatter entities into nonsensical fragments (their example: "BioNTech" -> [bio, ##nte, ##ch]), and homonymous acronyms like "WHO"/"US" collapse together as bags of word pieces
- **DyVo head** augments the wordpiece vocabulary with a Wikipedia entity vocabulary (~5.3M entities from KILT, filtered to those with Wikipedia2Vec embeddings) - 200x larger than a typical LSR wordpiece vocabulary
- Entities are scored, not exhaustively enumerated: an **entity candidate retrieval** component (entity linker, BM25, dense retriever, or an LLM) narrows millions of entities to a small per-query/per-document candidate set; the DyVo head then applies the same max-pool ReLU-log MLM scoring function used for word pieces to each candidate, producing a sparse bag of weighted entities
- Entity weights are **merged with wordpiece weights** into one joint sparse vector (Eq. 5, additive dot product over word dims + entity dims), stored and queried through a single inverted index - no separate retrieval pass or fusion step
- A trainable scaling factor lambda_ent (init 0.05) prevents entity weights from dominating and causing training collapse
- Best entity embeddings tested: LaQue (DistilBERT dense entity encoder, default) and BLINK (BERT-large), both beating Wikipedia2Vec skip-gram embeddings and generic dense passage encoders (DPR, JDS)
- Best entity candidates: few-shot generative retrieval (prompting Mixtral or GPT-4 to name relevant Wikipedia entities) beats entity linking (REL), BM25, and dense entity retrieval (LaQue) - and GPT-4-generated candidates are competitive with human-annotated candidates on CODEC

## Main findings

- On TREC Robust04 / TREC Core 2018 / CODEC (entity-rich news and complex-topic benchmarks), DyVo with linked entities (REL) beats the wordpiece-only LSR-w baseline on every metric (nDCG@10, nDCG@20, R@1000) across all three sparsity regularization settings tested
- At the sparsest setting (reg=1e-3) the entity gain is largest: nDCG@10 improves 1.15 to 3.57 points across datasets; at the least sparse setting (reg=1e-5) the gain narrows to roughly 1-2 nDCG points
- At reg=1e-5, LSR-w -> DyVo (REL): nDCG@10 Robust04 49.13 -> 51.19, Core 2018 40.99 -> 43.72, CODEC 52.61 -> 53.40; R@1000 Robust04 66.86 -> 68.56, Core 2018 63.22 -> 63.56, CODEC 69.07 -> 70.60
- Switching entity candidates from the REL linker to few-shot generative retrieval lifts nDCG@10/nDCG@20 by roughly +1.3 to +1.78 points across datasets; DyVo (GPT4) reaches nDCG@10 54.39 (Robust04), 43.06 (Core 2018), 56.46 (CODEC) - essentially matching DyVo (Human) on CODEC (56.42)
- Swapping in BLINK entity embeddings on top of GPT-4 candidates pushes further: nDCG@10 55.56 (Robust04), 44.63 (Core 2018), 58.15 (CODEC)
- DyVo (REL) beats BM25 (39.71-37.70 nDCG@10 range), BM25+RM3, zero-shot dense retrieval (DistilBERT-dot-v5, GTR-T5-base, Sentence-T5-base - all smaller or larger models), and LLM-based query expansion GRF (40.50 nDCG@10 on CODEC vs DyVo's 53.40)
- Simple token-aggregation entity embeddings (average static wordpiece embeddings of an entity's surface form) already yield roughly +1 nDCG point over LSR-w, evidence that much of the win comes from restoring whole-entity phrase matching, not just semantic embedding quality

## Key takeaways

- Entities can live as first-class dimensions in a sparse retrieval vocabulary alongside word pieces, scored the same way (max-pool dot product against a transformer's hidden states) and merged additively into one inverted-index-compatible vector - no separate entity index or late-fusion step
- The core mechanism generalizes directly to R47-H508: represent entities as dynamic sparse-vocabulary dimensions, merge their weights with wordpiece weights in a shared inverted index, and beat a SPLADE-style baseline specifically on entity-rich ranking because BPE tokenization shatters multi-token entity names into meaningless fragments
- Candidate quality dominates embedding quality: which entities get proposed (LLM-generated > linked > BM25/dense-retrieved) moves nDCG more than which embedding space represents them (LaQue/BLINK > Wikipedia2Vec > token-aggregation)
- The improvement is largest under tight sparsity budgets, meaning entity dimensions are most valuable exactly when word-piece dimensions are scarce - relevant if KGF's inverted-index budget is constrained
- LLM-generated entity candidates recover entities that are relevant but never explicitly mentioned in the text (their CODEC example: "Cryptocurrency" and "Bitcoin" for an NFT-investment query) - a capability entity linking alone cannot provide
- Reliance on LLMs (Mixtral, GPT-4) for candidate generation is explicitly flagged by the authors as a cost/latency limitation with no solution offered beyond distilling into a smaller ranker

## Tags

learned-sparse-retrieval, entity-linking, inverted-index, SPLADE, dynamic-vocabulary, entity-embeddings, sparse-retrieval, wikipedia-entities

## Source

https://arxiv.org/abs/2410.07722
