**Retrieval, Reward, and Training Protocols: What Matters in Training Search Agents? (2026)**

RL-trained search agents (Search-R1, GiGPO, IGPO, Tree-GRPO) each report gains under their own corpus, reward design, and training protocol, making it unclear what actually drives improvement. This controlled study reimplements all four under one shared GRPO codebase and isolates three variables. Headline finding: fixing a **295,331-document** gap in the standard Wiki-18 retrieval corpus produces a **2-6 EM point** swing per method - larger than the spread between the four training algorithms - and the simplest outcome-only reward (Search-R1) matches or beats three heuristic process-reward methods in most settings.

**Key mechanism**
- Retrieval-corpus audit: cross-checks every gold supporting document cited by HotpotQA, 2WikiMultihopQA, and MuSiQue training/validation splits against the widely used Wiki-18 dump, finds 295,331 missing, and builds a corrected "Wiki-fixed" corpus with those documents restored
- Four credit-assignment strategies reimplemented on a shared GRPO backbone for apples-to-apples comparison: Search-R1 (pure outcome reward, no step-level signal), GiGPO (cross-trajectory step grouping by state similarity), IGPO (per-turn change in log-probability of the correct answer as step reward), Tree-GRPO (prefix-sharing rollout trees for structural step comparison)
- Process evaluation protocol: replays 2,000 held-out annotated examples through trained vs. untrained models, decomposes trajectories into individual search steps, and measures per-step recall of supporting documents and overlap with previously retrieved documents
- Separately ablates training-data diversity (unique examples vs. repeated epochs at fixed compute), off-policy data usage, and search-budget scaling (max tool-call turns) at fixed total training steps

**Main findings**
- Corpus completeness dominates algorithm choice: training on Wiki-18 vs Wiki-fixed shifts average EM by 2-6 points per method - more than the gap between any two algorithms - and reshuffles method rankings (Search-R1 drops from 1st under Wiki-fixed to 3rd under Wiki-18)
- Of 3,321 training questions unanswerable under Wiki-18 (~10% of the training set), Search-R1 still answered 1,697 correctly at least once per rollout group, meaning roughly 866 training instances were producing gradient signal from parametric-memory guesses rather than real retrieval - noise confirmed systematic across all four methods (890/698/859 comparable cases for GiGPO/IGPO/Tree-GRPO)
- Outcome-only reward is competitive or better: on Qwen3-8B/Hermes format, Search-R1 reaches 49.49 avg EM vs GiGPO 47.23, IGPO 49.12, Tree-GRPO 44.63 across five benchmarks (2Wiki, Bamboogle, HotpotQA, Musique, PopQA)
- Process-level credit assignment trades off recall vs turn count: comparing trained vs untrained models on step-level query recall, 3 of 4 methods (Search-R1 -4.50, Tree-GRPO -2.79, IGPO -0.53) *decrease* per-step recall after training while GiGPO improves recall by ~10 points but cuts search depth sharply - no method improves both simultaneously
- IGPO's information-gain step reward tends toward over-searching (avg 3.00 turns, some redundant), GiGPO toward under-searching (avg 1.67 turns, higher per-step quality) - the credit-assignment heuristic measurably biases search behavior, not just final accuracy

**Key takeaways**
- Before comparing search-agent training algorithms, verify the retrieval corpus is complete for the benchmark's gold evidence - an incomplete corpus both understates true performance and can invert the ranking between methods
- Process-level (step) reward is not a free win over outcome-only reward; each tested heuristic overcorrects search behavior in a specific direction (too many turns, too few turns, retrieval redundancy) without a method that improves both accuracy and search quality together
- The simplest RL recipe (Search-R1's outcome-only reward) remains a strong, low-complexity baseline that more elaborate credit-assignment schemes must clear before their added complexity is justified

**Relevance**
- Directly on-corpus for KGF: the study's benchmark family (HotpotQA, 2WikiMultihopQA, MuSiQue) is the same family KGF's bench-only scale ladder uses, and the corpus-completeness finding is a direct warning to audit KGF's own retrieval corpus for gold-document coverage gaps before drawing conclusions from any RL-navigator A/B
- For R51 RL navigators, the negative result on process-reward heuristics (GiGPO/IGPO/Tree-GRPO) argues for starting any KGF traversal-policy RL experiment from a Search-R1-style outcome-only baseline rather than building step-level reward machinery first

**Tags**
- #ReinforcementLearning
- #SearchAgents
- #RewardDesign
- #MultiHopQA
- #RetrievalCorpus

**Source**
- Download: https://arxiv.org/abs/2605.27881
- Local: [paper] What Matters in Training Search Agents, 2026.pdf
