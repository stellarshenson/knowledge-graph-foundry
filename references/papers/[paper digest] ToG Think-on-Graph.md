**Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph (ToG), Sun, Xu, Tang, Wang, Lin, Gong, Ni, Shum, Guo, ICLR 2024 (arXiv 2307.07697)**

The canonical LLM-as-agent beam search over a KG. SOTA on **6 of 9** datasets training-free: CWQ **69.5** (ToG-R w/ GPT-4; prior FT SOTA 70.4), WebQSP **82.6**, GrailQA **81.4**, all exact match. Gain over CoT grows with backbone: +18.5 CWQ (Llama-2-70B) → +23.5 (GPT-4). The cost: **2ND+D+1 LLM calls per question** at beam width N and depth D; the default N=D=3 means **22 calls per question** (measured avg 22.6 calls / 9,669 tokens / 96.5 s on CWQ per PoG's efficiency study).

**Key mechanism**
- LLM⊗KG paradigm: the LLM iteratively explores entities and relations on the KG (Freebase/Wikidata), beam search keeping top-N paths to depth Dmax=3
- Per step: relation exploration (LLM prunes candidate relations), entity exploration (LLM prunes candidate entities), reasoning check (LLM decides if paths suffice to answer)
- ToG-R variant keeps relation chains only (no intermediate entities) - slightly better on CWQ, worse elsewhere
- Triple-format prompts beat sentence-format for path representation (58.8 vs 58.6 CWQ, larger gaps for ToG-R)

**Main findings**
- Performance grows with depth/width but plateaus past depth 3 - few questions have reasoning depth > 3; cost grows linearly with depth
- Replacing the LLM pruner with BM25/SentenceBERT cuts calls to D+1 but costs -8.4 (CWQ) / -15.1 (WebQSP) points - the LLM in the loop IS the accuracy
- Weakest on single-hop KBQA (SimpleQuestions 66.7 vs FT SOTA 85.8) - the walk pays off only on multi-hop
- Knowledge traceability: explicit paths let users/LLMs backtrack and correct stale KG triples

**Key takeaways**
- The agentic walk buys multi-hop accuracy with a ~20x LLM-call bill over single-shot RAG - for KGF this is the adversary baseline the single-shot bridge must beat cost-adjusted
- The diminishing-returns depth (3) and the LLM-pruner dependency define the walk's floor cost; there is no cheap variant that keeps the accuracy
- Traceable paths as a response artifact (not the walk itself) are worth stealing for a one-shot render

**Tags**: #ToG #AgenticRetrieval #BeamSearch #KGQA #LLMAgent #TokenCost #ICLR

**Source**: https://arxiv.org/abs/2307.07697. Local: [paper] ToG Think-on-Graph, 2023-07.pdf
