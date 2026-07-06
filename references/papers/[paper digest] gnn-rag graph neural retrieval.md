**GNN-RAG: Graph Neural Retrieval for Efficient LLM Reasoning on Knowledge Graphs (2024)**

GNN-RAG replaces expensive LLM-driven KG traversal with a lightweight GNN retriever that issues zero LLM calls during retrieval. A GNN scores answer candidates over a dense KG subgraph; shortest paths from question entities to top candidates are verbalized and handed to the LLM. With a 7B tuned LLM it matches or beats GPT-4-based ToG (**90.7% vs 82.6% Hit** on WebQSP) at **~9x fewer** KG tokens.

**Key mechanism**
- A GNN scores answer candidates over a dense KG subgraph by question and neighbor relevance
- Shortest paths from question entities to top candidates are extracted and verbalized
- The verbalized paths are handed to the LLM - no LLM calls during retrieval

**Main findings**
- WebQSP F1 71.3 / Hits@1 80.6 (73.5 / 82.8 with retrieval augmentation)
- CWQ F1 59.4 / Hits@1 61.7
- Beats GPT-4-based ToG (90.7% vs 82.6% Hit on WebQSP) with a 7B tuned LLM
- Outperforms LLM-based retrieval on multi-hop/multi-entity questions by 8.9-15.5 F1 points
- ~9x fewer KG tokens (median 144-281 input tokens)

**Key takeaways**
- GNN retrieval clearly wins on many-hop, many-entity KGQA
- Removing LLM calls from retrieval cuts both cost and token load
- Requires thousands of QA training examples

**Relevance**
- Strongest evidence GNN retrieval helps on a bottleneck we do not have - our evidence is 100% within 2 hops of seeds
- Frames the honest null hypothesis that GNN retrieval offers little at our scale
- Needs thousands of QA training examples we lack

**Tags**
- #GraphRAG #GNN #Retrieval #KGQA

**Source**
- Download: https://arxiv.org/pdf/2405.20139
- Local: [paper] gnn-rag graph neural retrieval, 2024.pdf
