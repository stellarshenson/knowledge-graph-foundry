**GFM-RAG: Graph Foundation Model for Retrieval Augmented Generation (2025)**

GFM-RAG is the first graph foundation model for RAG that transfers to unseen datasets without fine-tuning. It builds a KG index over a document corpus, then a query-dependent GNN reasons over the graph structure to retrieve in a single step, explicitly designed to be robust to noise and incompleteness in the constructed graph. Pretrained on **60 KGs** spanning **>14M triples** and **700k documents**, it reaches SOTA across three multi-hop QA and seven domain RAG datasets.

**Key mechanism**
- Build a KG index over a document corpus
- A query-dependent GNN (8M parameters) reasons over graph structure for multi-hop query-knowledge relationships
- Retrieval happens in a single step
- Architecture explicitly designed robust to noise/incompleteness in the constructed graph

**Main findings**
- Pretrained two-stage on 60 KGs spanning >14M triples and 700k documents
- SOTA across three multi-hop QA and seven domain RAG datasets
- Follows neural scaling laws

**Key takeaways**
- A single pretrained graph model can retrieve zero-shot on a new graph
- Single-step retrieval avoids iterative traversal
- Noise-robustness is a design claim to be tested, not assumed

**Relevance**
- The only GraphRAG mechanism that runs zero-shot on our graph - a cheap fair test of whether learned graph retrieval beats 2-hop vector seeding
- Honest expectation is a null result at our scale
- Noise-robustness claim worth probing against our known 47 duplicates

**Tags**
- #GraphRAG #FoundationModel #GNN #Retrieval

**Source**
- Download: https://arxiv.org/pdf/2502.01113
- Local: [paper] gfm-rag graph foundation model rag, 2025.pdf
