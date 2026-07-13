**RECOMP: Improving Retrieval-Augmented LMs with Compression and Selective Augmentation, Xu, Shi & Choi (UT Austin / U Washington), 2023-10**

Trains a small compressor that sits between retrieval and the frozen reader LM, turning N retrieved documents into a short query-focused summary - or an empty string when nothing retrieved helps. Two compressor types: an extractive dual-encoder that selects useful sentences, and an abstractive encoder-decoder distilled from GPT-3.5. On open-domain QA with Flan-UL2 (20B) as reader, the trained abstractive compressor reaches NQ EM **37.04** at **5%** of the tokens of the top-5-document baseline (**2 EM** points below full documents), and on TQA **58.68** EM at **5%** tokens (**3.7 EM** points below full). The trained extractive compressor does best on HotpotQA, holding **11%** compression rate at only **2.4 EM** points below full documents. Oracle compressors hit compression rates as low as **6%** on language modeling with no perplexity loss, showing large headroom above the trained models.

**Key mechanism**
- Extractive compressor: dual-encoder trained with a contrastive objective - for each input x, sentences are ranked by whether prepending them lowers the reader's loss / raises answer accuracy more than a threshold ϵ over other candidates
- Abstractive compressor: encoder-decoder (T5-based) distilled from GPT-3.5 query-focused summaries, since no human-annotated summaries exist for this end-task-driven objective
- Selective augmentation: the abstractive compressor can emit an empty string when retrieved documents add nothing, avoiding the accuracy hit from prepending irrelevant context
- Reader LM stays frozen and black-box throughout - only the compressor is trained, so it is far smaller than the reader (T5-large 770M-class vs Flan-UL2 20B)

**Main findings**
- QA (Flan-UL2, top-5-doc baseline): NQ 39.39 EM at 660 tokens -> trained abstractive 37.04 EM at 36 tokens; TQA 62.37 EM at 677 tokens -> 58.68 EM at 32 tokens; HotpotQA 32.80 EM at 684 tokens -> trained extractive 30.40 EM at 75 tokens
- Language modeling (GPT-2/GPT2-XL/GPT-J, WikiText-103): oracle compressors reach 6-13% of top-5-document tokens with no perplexity increase; trained compressors reach 25% compression with minimal drop and transfer across model scales (compressor trained on GPT-2 improves GPT2-XL and GPT-J perplexity too)
- Selective augmentation fires often: 4-24% of training examples get an empty abstractive summary; on the LM task, summaries are prepended to only 33% of examples
- Reduces incorrect answer-copying from irrelevant context: model copies from context incorrectly 39% of the time with the trained compressor's summaries vs 81% (top-5 documents) and 85% (GPT-3.5 summaries)
- Manual faithfulness/comprehensiveness annotation (30 samples per dataset): the small trained abstractive compressor is less faithful than GPT-3.5 but more comprehensive; both models are most faithful on TQA and least faithful on HotpotQA, explaining the smaller HotpotQA gains
- Heuristic phrase-level compression (bag-of-words, named entities) underperforms prepending full uncompressed documents - naive truncation hurts more than it saves

**Key takeaways**
- A small trained compressor between retriever and reader is a cheap, model-agnostic way to cut context tokens while improving or matching accuracy - the summary is end-task-trained, not human-summarization-trained
- Selective augmentation (empty-string abstention) is a first-class output, not a fallback - the compressor learns when retrieval helps at all
- Multi-hop tasks (HotpotQA) expose the ceiling of single-summary abstraction: extractive selection beats abstractive synthesis when evidence must be combined across documents rather than compressed into one narrative
- Compressed summaries transfer across reader LMs better than soft-prompt compression approaches, because they stay in natural language

**Tags**: #RECOMP #ContextCompression #SelectiveAugmentation #RetrievalAugmentedLM #QueryFocusedSummarization

**Relevance to Knowledge Graph Foundry**: KGF's PPR-seeded retrieval already returns a small, high-precision entity/passage set (dense@16=0.854), but the H382 context-escalation gate and R48 community-segmentation work both wrestle with how much material to hand the reader once escalation fires - RECOMP's selective, end-task-trained compressor (including its learned empty-string abstention) is a candidate mechanism for that escalation step, compressing escalated Leiden-community or multi-hop context before it reaches the local vLLM gpt-oss-120b reader rather than prepending it whole.

**Source**: https://arxiv.org/abs/2310.04408. Local: [paper] RECOMP, 2023.pdf
