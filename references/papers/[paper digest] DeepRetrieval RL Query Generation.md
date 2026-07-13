**DeepRetrieval: Hacking Real Search Engines and Retrievers with Large Language Models via Reinforcement Learning (2025)**

Prior LLM query-augmentation methods need supervised query-rewriting pairs or distillation from a bigger model. DeepRetrieval instead trains a small LLM to generate augmented queries using actual retrieval performance (recall, NDCG, execution accuracy) as the RL reward, with no reference queries required. A **3B-parameter** DeepRetrieval model outperforms GPT-4o and Claude-3.5-Sonnet on **11 of 13** retrieval/SQL datasets, and on real-world literature search engines reaches **65.07% recall** for publication search versus a previous SOTA of 24.68%, and **63.18%** for trial search versus 32.11%.

**Key mechanism**
- Formulated as an RL problem: state = original query, action = LLM-generated augmented query, reward = task-specific retrieval metric obtained by actually issuing the augmented query against the real search engine or retriever
- Reward combines a retrieval-performance term and a format-adherence term: `r(q,q') = r_retrieval(q,q') + r_format(q')`; retrieval metric is Recall@K for literature search, hit rank for evidence-seeking, NDCG@K for classic IR, execution accuracy for SQL
- Model is prompted to first produce an explicit `<think>` reasoning span, then an `<answer>` span containing the final augmented query (structured boolean expression for literature search, natural-language expansion for dense retrieval, or SQL for database search)
- Optimized with PPO under a KL-regularized objective against a reference policy, implemented on the HybridFlow (verl) RL infrastructure; algorithm-agnostic, GRPO is noted as a drop-in alternative
- No supervised query-rewriting labels are used anywhere in training - the model discovers augmentation strategies purely from retrieval outcomes

**Main findings**
- Literature search on real engines (PubMed, ClinicalTrials.gov), Recall@3K: publication search 65.07% vs previous SOTA 24.68%; trial search 63.18% vs previous SOTA 32.11%
- A 3B DeepRetrieval model beats GPT-4o and Claude-3.5-Sonnet prompted baselines on 11 of 13 evaluated datasets spanning literature search, evidence-seeking retrieval, classic sparse/dense IR, and SQL database search
- Gains hold across five distinct retrieval domains without any architecture change - only the reward function's target metric changes per domain
- Demonstrates that reward-shaped RL on real retrieval outcomes generalizes across structurally different query formats (boolean expressions, NL expansions, SQL) using the same think-then-answer training recipe

**Key takeaways**
- Retrieval metrics computed against a live search backend are a viable, label-free reward signal for training query generation - this removes the need for expensive human-annotated query-rewrite pairs entirely
- A small (3B) RL-trained model can outperform much larger prompted frontier models specifically on the query-formulation sub-task, suggesting task-specific RL training beats scale for this narrow skill
- The approach is validated per-domain with domain-specific reward metrics; portability to a new retrieval domain requires defining a new task-appropriate reward, which is nontrivial design work each time

**Relevance**
- Directly relevant to R51 RL navigators: DeepRetrieval's live-retrieval-reward recipe is a template for training a small KGF query-reformulation or graph-traversal-query model against actual KGF retrieval/recall metrics rather than supervised query pairs
- The domain-agnostic think-then-answer format with a swappable reward function suggests KGF could reuse the same training loop for both dense-retrieval query augmentation and structured (Cypher-like) graph query generation by changing only the reward

**Tags**
- #ReinforcementLearning
- #QueryGeneration
- #InformationRetrieval
- #RewardShaping
- #SmallModelEfficiency

**Source**
- Download: https://arxiv.org/abs/2503.00223
- Local: [paper] DeepRetrieval RL Query Generation, 2025.pdf
