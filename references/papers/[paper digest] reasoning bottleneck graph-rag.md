**The Reasoning Bottleneck in Graph-RAG: Structured Prompting and Context Compression for Multi-Hop QA (2026)**

Evaluating KET-RAG on HotpotQA, MuSiQue, and 2WikiMultiHopQA, the authors find retrieval already works - **77% to 91%** of questions have the gold answer somewhere in the retrieved context - yet overall accuracy is only **35% to 78%**, because **73% to 84%** of all errors are reasoning failures, not retrieval failures. The paper's fix is inference-time only: no retraining, no re-indexing, just better prompting and context filtering, and it lets a fully augmented **Llama-8B model match or exceed an unaugmented Llama-70B baseline at ~12x lower cost**.

**Key mechanism**
- Error decomposition: split every wrong answer into retrieval failure (gold answer absent from context) vs. reasoning failure (present but the model got it wrong), isolating the true bottleneck
- SPARQL chain-of-thought prompting: a single modified LLM call that asks the model to decompose the question into triple-pattern queries aligned with the retrieved entity-relationship structure, rather than free-form reasoning over a token wall
- Graph-walk context compression: a post-retrieval, no-LLM-call breadth-first traversal from question entities through the knowledge graph, keeping only structurally connected context and cutting input tokens by ~60%
- Question-type routing: dispatches easier question types to the cheap augmented small model and harder types to a stronger model, driving the overall cost win

**Main findings**
- Context coverage is high (77-91%) but raw accuracy is far lower (23-67% for Llama-3.1-8B, 35-78% for Llama-3.3-70B) - the gap is the reasoning bottleneck, confirmed by the 73-84% reasoning-failure share of errors
- SPARQL CoT alone improves accuracy by **+2 to +14 pp** across benchmarks and models
- Graph-walk compression adds a further **+6 pp on average** when paired with structured prompting on smaller models, while cutting tokens ~60%
- Combined augmentations let an 8B model match or beat a 70B baseline on all three benchmarks at ~12x lower inference cost
- Replication on LightRAG (a different Graph-RAG system) confirms the augmentations transfer, not a KET-RAG-specific artifact

**Key takeaways**
- Once retrieval coverage is already high, throwing more retrieval effort at a Graph-RAG system is the wrong lever - the marginal gain lives in how the model reasons over the retrieved graph context, not in retrieving more of it
- Structuring the prompt around the graph's native entity-relationship shape (SPARQL-style decomposition) outperforms generic chain-of-thought on graph-derived context
- Compressing context via graph structure (not summarization) is a free accuracy lever, not just a cost lever - it removes distractor content a needle-in-a-haystack model would otherwise have to filter itself
- The gains are model-index-independent: because the graph index doesn't change, better future LLMs slot in without re-indexing

**Relevance**
- Directly names the KGF REG-2 failure class: high context coverage with low accuracy is exactly a reasoning-bottleneck signature, not a retrieval-completeness signature, and this paper gives concrete numbers and a fix that requires no ingest-time changes
- The graph-walk compression technique (BFS from question entities, structural pruning, no LLM call) is a candidate cheap pre-answering pass to test on KGF's own multi-hop retrieval path
- SPARQL CoT is a directly portable prompt-structuring idea for KGF's answer-generation stage given its typed entity-relationship graph

**Tags**
#GraphRAG #MultiHopQA #ContextCompression #ChainOfThought #ReasoningBottleneck

**Source**
- Download: https://arxiv.org/pdf/2603.14045
- Local: [paper] reasoning bottleneck graph-rag, 2026.pdf
