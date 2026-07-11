**Graph Chain-of-Thought: Augmenting Large Language Models by Reasoning on Graphs (Graph-CoT), Jin, Xie, Zhang, Roy, Zhang, Li, Li, Tang, Wang, Meng, Han, ACL Findings 2024 (arXiv 2404.07103)**

Defines the structured graph-API-for-agents pattern and the GRBench benchmark: **1,740 questions over 10 domain graphs** (academic, e-commerce, literature, healthcare, legal). Iterative loop of LLM reasoning → graph function call → execution. Average GPT4score **36.29** vs 23.09 for 1-hop subgraph RAG, 16.63 for node retrieval, 19.48 for the base LLM (GPT-3.5 backbone).

**Key mechanism**
- Four-function graph API the LLM calls in-context: RetrieveNode(text) semantic search, NodeFeature(id, feature), NeighborCheck(id, type), NodeDegree(id, type)
- Each iteration = reasoning, interaction (generate the function call), execution (run it, return result); loop until Finish
- Pure in-context learning - no training; demonstrations are load-bearing: zero-shot (no demos) collapses to ~0 on ALL datasets
- Baseline framing: subgraph linearization explodes with hops - 2-hop ego-graphs SCORE WORSE than 1-hop (22.12 vs 23.09, lost-in-the-middle)

**Main findings**
- Backbone matters: GPT-4 46.28, GPT-3.5 36.63, Mixtral-8x7b 36.46, Llama-2-13b 16.04 GPT4score
- Difficulty cliff: easy questions 53-80, medium/hard 2.5-31 - the agentic loop does not rescue complex/inductive reasoning
- Failure modes: wrong function calls from lexical (not semantic) matching; misunderstanding the graph schema (calling neighbor types that do not exist)
- Absolute scores stay low (36 avg) - the authors concede large headroom

**Key takeaways**
- The multi-round graph API is a conversation, and every round is an LLM call - the antithesis of a one-response bridge contract
- The 2-hop-worse-than-1-hop result independently confirms KGF's retrieval-first doctrine: bigger walks poison context; scoped 1-hop context wins
- The schema-misunderstanding failure class argues for a bridge that returns assembled context, not one that expects the caller to navigate KGF's schema

**Tags**: #GraphCoT #GRBench #AgenticRetrieval #GraphAPI #LLMAgent #LostInTheMiddle

**Source**: https://arxiv.org/abs/2404.07103. Local: [paper] Graph-CoT, 2024-04.pdf
