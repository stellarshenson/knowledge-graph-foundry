**SiReRAG: Indexing Similar and Related Information for Multihop Reasoning, Zhang, Liu, Xiong, Zhou, Yavuz, Nguyen, Murthy, Yang, Xu, et al. (Salesforce AI Research / Yale), ICLR 2025 (arXiv 2412.06206)**

The RAG-side statement that **similarity and relatedness are two different indexing axes** and that a multi-hop index needs both. Existing RAG indices are built either on semantic similarity (embedding clusters) or on relatedness (entity/graph structure), and each alone misses the other's evidence.

**Key mechanism**
- **Similarity tree**: recursive summarisation over semantically similar text, giving a hierarchy of abstractions
- **Relatedness tree**: extract propositions and their entities, group text by shared entity, and recursively summarise those groups
- Both trees' nodes go into one flat retrieval pool, so a query can hit either axis; retrieval is plain similarity search over the union

**Main findings**
- Consistent improvements over state-of-the-art baselines on multi-hop datasets (MuSiQue, 2WikiMultiHopQA, HotpotQA), reported as gains of roughly 1.9 points average F1 over the strongest prior indexing method
- Ablations show removing either tree degrades performance - the axes are complementary, not redundant

**Key takeaways**
- Independent confirmation that entity-relatedness structure recovers evidence dense similarity misses on exactly the 2WikiMultiHopQA family
- The published integration pattern is **union of two indices at retrieval time**, not fusion of the two signals into one score - the same conclusion the dense-PRF literature reaches from the failure side
- Reported deltas on multi-hop QA from a whole additional index are low single-digit F1, which calibrates the plausible size of any single new retrieval mechanism on this benchmark family

**Tags**: #SiReRAG #MultiHop #Relatedness #Indexing #2Wiki #R59

**Source**: https://arxiv.org/abs/2412.06206. Local: [paper] SiReRAG Similar and Related Multihop, 2024.pdf
