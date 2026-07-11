**Interleaving Retrieval with Chain-of-Thought Reasoning for Knowledge-Intensive Multi-Step Questions (IRCoT), Trivedi, Balasubramanian, Khot, Sabharwal, ACL 2023 (arXiv 2212.10509)**

The canonical iterative text-retrieval baseline every single-shot system is priced against. Interleaves CoT sentences with retrieval: each generated reasoning sentence becomes the next BM25 query. Retrieval recall up to **+21 points**, answer F1 up to **+15 points** over one-step retrieve-and-read (GPT-3 code-davinci-002) on HotpotQA, 2WikiMultihopQA, MuSiQue, IIRC. The bill: **2-4 retrieval rounds** per question, top-10 passages per step, every round an LLM generation - HippoRAG measures IRCoT at **\$1-3 per 1,000 queries and 20-40 minutes vs its own \$0.1 and 3 minutes** (10-30x cost, 6-13x latency) for comparable or worse recall.

**Key mechanism**
- Loop: retrieve K paragraphs → generate one CoT sentence conditioned on all accumulated paragraphs → use that sentence as the next query → repeat until "answer is:" or 15-paragraph cap
- Thesis: what to retrieve depends on what has been derived - one-step retrieval structurally cannot see hop-2 vocabulary
- Separate post-hoc reader over the accumulated paragraphs beats extracting the answer from the retrieval-time CoT
- No training; works from Flan-T5-base (0.2B) to GPT-3 (175B)

**Main findings**
- Per-dataset GPT-3 retrieval gains: HotpotQA +11.3, 2WikiMultihopQA +22.6, MuSiQue +12.5, IIRC +21.2
- QA F1 gains: +7.1 / +13.2 / +7.1 (IIRC flat - parametric knowledge already covers it)
- Halves factual errors in generated CoTs vs one-step retrieval (-50% HotpotQA, -40% 2Wiki)
- Gains hold out-of-distribution and for 0.2B models

**Key takeaways**
- The recall gap IRCoT exposes is real - but HippoRAG 1/2 close most of it in ONE PPR pass by moving the multi-hop work to ingest-time graph structure - the load-bearing precedent for KGF's bridge
- IRCoT is the honest upper-cost pole: any KGF escalation rung must show it recovers the IRCoT-class gap at a fraction of the 2-4-round bill
- Sentence-as-next-query is the cheapest reformulation primitive if KGF ever needs a bounded second round

**Tags**: #IRCoT #IterativeRetrieval #MultiHopQA #QueryDecomposition #TokenCost #AdversaryBaseline

**Source**: https://arxiv.org/abs/2212.10509. Local: [paper] IRCoT, 2022-12.pdf
