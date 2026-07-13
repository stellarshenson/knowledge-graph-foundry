**LIMRANK: Less is More for Reasoning-Intensive Information Reranking (2025)**

The paper asks whether reasoning-intensive rerankers need the large-scale fine-tuning corpora prior work assumes. It builds LIMRANK-SYNTHESIZER, a bottom-up pipeline that expands simple MS MARCO seed queries into diverse, persona-driven, reasoning-annotated training examples, then fine-tunes a pointwise reranker (LIMRANK) on the result. Trained on **less than 5% of the data typically used in prior work**, LIMRANK matches or beats the strongest reasoning rerankers: **28.0 nDCG@10** average on BRIGHT versus RANK1-7B's 27.5, and **30.3% accuracy** on GPQA-RAG versus RANK1's 28.3%.

**Key mechanism**
- Seeds from MS MARCO simple queries, expanded via sampled personas (from PersonaHub) into "daily-life" and "expert-domain" query variants
- An LLM (GPT-4o) generates long chain-of-thought reasoning traces per query, then derives positive and hard-negative passage descriptions from those traces before materializing the passages
- Data generation follows an explicit guideline covering query domain diversity, difficulty diversity, well-structured and human-verified reasoning chains, and hard-negative complexity diversity
- DeepSeek-R1 filters the synthesized set for quality before it becomes training data
- Only ~20K high-quality examples are needed versus the hundreds of thousands used by comparable rerankers

**Main findings**
- BRIGHT (reasoning-intensive retrieval, nDCG@10): LIMRANK 28.0 average vs RANK1-7B 27.5, RankLLaMA-7B 23.9, Monot5-3B 24.5
- FollowIR (instruction-following retrieval, p-MRR): LIMRANK 1.2 vs RANK1-7B 0.3, FollowIR-7B 0.3
- Downstream tasks: LitSearch Recall@5 60.1% (comparable to RANK1's 60.8%); GPQA-RAG accuracy 30.3%, best of all compared rerankers
- Ablation on synthesis components: removing daily-life queries drops FollowIR from 1.19 to 0.39; removing long reasoning traces drops it to 1.17 - the reasoning-trace and persona-query components are the biggest individual contributors
- Controlled comparison at fixed 20K-example scale: LIMRANK-synthesized data outperforms RANK1, Promptriever, and ReasonIR synthetic data on the same reranker architecture, isolating synthesis quality (not just scale) as the driver
- Performance plateaus below a minimum data size - the "less is more" effect does not extend to arbitrarily small sets

**Key takeaways**
- Reasoning-intensive reranking quality is bottlenecked by data quality (diverse, persona-grounded, CoT-annotated) more than by data volume - a small model trained on a well-designed 20-40K set closes most of the gap to large-corpus rerankers
- A reusable, LLM-driven synthesis pipeline (persona sampling to CoT to positive/negative passage generation) is a practical recipe for building a project-specific reranker training set without expensive human annotation
- The approach is validated only for pointwise rerankers; listwise/setwise transfer is untested

**Relevance**
- Direct blueprint for R51 small-model scorer distillation: the LIMRANK-SYNTHESIZER pipeline (seed queries to persona expansion to CoT-grounded positive/negative generation to filtering) is a template for distilling a compact KGF-specific relevance scorer from a larger judge model
- The <5% data-efficiency result suggests a small scorer can be trained cheaply once KGF has a modest labeled evidence set, without needing MS MARCO-scale supervision

**Tags**
- #Reranking
- #DataEfficiency
- #SyntheticData
- #ReasoningIntensiveRetrieval

**Source**
- Download: https://arxiv.org/abs/2510.23544
- Local: [paper] LimRank Reasoning-Intensive Reranking, 2025.pdf
