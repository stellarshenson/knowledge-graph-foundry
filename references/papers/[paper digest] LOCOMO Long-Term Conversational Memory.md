**LOCOMO: Evaluating Very Long-Term Conversational Memory of LLM Agents, Maharana et al. (UNC Chapel Hill / USC / Snap Inc.), 2024-02**

A machine-human pipeline generates **50 very long-term dialogues** grounded on personas and temporal event graphs, each averaging **304.9 turns, 19.3 sessions, and 9,209.2 tokens** (9x MSC's average length) with image-sharing/reacting behaviour; human annotators edited **~15% of dialog turns** and removed/substituted **~19% of images** from the LLM-generated draft. On the resulting QA benchmark (**7,512 questions** across five reasoning categories), the best base model **GPT-4-turbo reaches only 32.1 overall F1** against a **human ceiling of 87.9 F1**, and long-context **GPT-3.5-turbo-16K's adversarial-question F1 collapses to 2.1%** (vs 70.2% for 4K-context GPT-4-turbo), showing that wider context windows induce hallucination rather than fixing memory.

**Key mechanism**
- Generation pipeline: LLM agents authored on personas + a temporal event graph produce multi-session dialogues; a separate LLM inserts/substitutes shareable images; human annotators verify and edit for long-range consistency and event-graph grounding
- Evaluation benchmark has three tasks: question answering (5 categories), event summarization (scored via FactScore, not BLEU/ROUGE, for factual accuracy), and multimodal dialogue generation
- QA categories: single-hop (36%, one session), multi-hop (14.6%, synthesis across sessions), temporal reasoning (20.6%), open-domain knowledge (3.9%, requires external commonsense/world facts), adversarial (24.9%, no true answer exists - correct behaviour is to identify the question as unanswerable)
- RAG variants compared at multiple top-k: raw dialog turns, extracted "observation" assertions per speaker, and session-level summaries, retrieved with DRAGON

**Main findings**
- Retrieving observations beats raw dialog and beats summaries; a **5% F1 gain** appears at top-5 observations for gpt-3.5-turbo but the gain **falters as top-k grows**, indicating retrieved-context signal-to-noise ratio (not recall) is the binding constraint - recall@25 already reaches 87.5-97.3% for dialog retrieval yet F1 stays far below human level
- Temporal reasoning and open-domain knowledge are the hardest categories across every model/method combination tested
- Long-context models are more prone to hallucinating an answer to unanswerable (adversarial) questions than short-context models, despite ingesting more of the conversation
- Session-summary RAG has high recall accuracy (up to 90.7% overall) but does not translate to better F1, attributed to information loss in the dialog-to-summary conversion

**Key takeaways**
- Length and turn-count alone (9K tokens, 300 turns, 35 sessions) already break both raw long-context and naive RAG memory; the gap to human performance (87.9 vs ~32-38 F1) is the headline number, not any single model's score
- The adversarial category operationalizes abstention as a first-class metric - a model that answers everything scores worse than one that correctly declines
- FactScore substitutes for BLEU/ROUGE specifically because lexical-overlap metrics do not penalize factually wrong but fluently-worded event summaries

**Relevance to Knowledge Graph Foundry**: LOCOMO is a benchmark the conversational-memory peer field (mem0, Zep, supermemory, graphify) publishes against, distinct from KGF's 2wiki multi-hop line (GraphRAG/LightRAG/HippoRAG-2); its adversarial/unanswerable question category is the same abstention concept KGF's gap-ledger targets and that LongMemEval separately measures, so LOCOMO's F1-on-adversarial-questions metric is a candidate proxy for scoring KGF's own abstention behaviour if a conversational-memory comparison is ever added to the campaign.

**Tags**: #LOCOMO #ConversationalMemory #LongTermMemory #RAG #Abstention #TemporalReasoning

**Source**: https://arxiv.org/abs/2402.17753. Local: [paper] LOCOMO Long-Term Conversational Memory, 2024.pdf
