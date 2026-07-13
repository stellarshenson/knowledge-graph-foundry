**LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory, Wu et al. (UCLA, Tencent AI Lab, UC San Diego), 2024-10**

Benchmark of **500** manually curated questions testing five core long-term memory abilities - information extraction, multi-session reasoning, knowledge updates, temporal reasoning, and abstention - embedded in freely scalable user-assistant chat histories. Two standard settings: LongMemEval-S at **~115k tokens** per problem and LongMemEval-M at **500 sessions (~1.5 million tokens)**. Commercial memory-augmented assistants (ChatGPT, Coze) show **30% and 64% accuracy drops** respectively versus offline full-context reading with the same underlying LLM (GPT-4o); long-context LLMs reading the full LongMemEval-S history drop **30% to 60%** versus oracle-retrieval accuracy (GPT-4o: 0.870 oracle to 0.606 full-history, a 30.3% drop; Llama 3.1 70B: 0.744 to 0.334, a 55.1% drop).

**Key mechanism**
- Unifies memory-augmented chat assistants into three stages - indexing, retrieval, reading - with four control points: value, key, query, reading strategy
- Value granularity: decomposing sessions into individual rounds beats whole-session or summary/fact values for QA accuracy; fact decomposition specifically helps multi-session reasoning
- Key expansion: concatenating the value with an LLM-extracted user fact as an additional key (K = V + fact) improves recall@k by **9.4%** and downstream accuracy by **5.4%** on average over using the value alone as the key
- Time-aware indexing and query expansion (tagging values with event dates, extracting a query time range at retrieval) improves temporal-reasoning recall by **6.8% to 11.3%**, but only when a strong LLM performs the time-range extraction (Llama 3.1 8B hallucinates time ranges)
- Reading strategy: Chain-of-Note plus structured JSON formatting of retrieved items lifts oracle-retrieval QA accuracy by up to **10 absolute points** for GPT-4o (0.862 to 0.924) even under perfect retrieval, showing reading strategy alone is a major error source
- Questions built via a 164-attribute ontology (lifestyle, belongings, life events, situational context, demographics), LLM-generated evidence statements woven into synthetic chat sessions, with 30 evidence questions rewritten as false-premise questions to test abstention
- Automatic grading uses gpt-4o-2024-08-06 as judge, validated at **>97% agreement** with human experts

**Main findings**
- Five abilities, seven question types (single-session-user, single-session-assistant, single-session-preference, multi-session, knowledge-update, temporal-reasoning, abstention)
- Round-level value + fact-augmented key + time-aware query expansion + Chain-of-Note/JSON reading is the paper's recommended composite design, and each control point contributes independently
- Retrieval quality and reading quality are separable failure modes - Table 3/4 numbers show recall gains from key design, Figure 6 shows reading-strategy gains persist even at oracle recall

**Key takeaways**
- A working retrieval pipeline is necessary but not sufficient - reading strategy (CoN + structured format) recovers points that better retrieval alone cannot
- Abstention is evaluated as a first-class ability via false-premise questions, not inferred from confidence scores
- Benchmark and code released at https://github.com/xiaowu0162/LongMemEval

**Relevance to Knowledge Graph Foundry**: LongMemEval is the conversational-memory peer bench (mem0, Zep, supermemory, graphify publish results here) sitting alongside 2wiki/GraphRAG/LightRAG/HippoRAG-2 in the public benchmark campaign; its abstention-as-first-class-ability framing (false-premise questions graded "I don't know") is the closest published precedent for KGF's gap-ledger abstention signal, and its key-expansion/time-aware-indexing findings (index-time enrichment beats retrieval-time cleverness) reinforce KGF's retrieval-first principle of pushing work to ingest time.

**Tags**: #LongMemEval #ConversationalMemory #Abstention #Benchmark #ChatAssistants

**Source**: https://arxiv.org/abs/2410.10813. Local: [paper] LongMemEval, 2024.pdf
