**Search-R1: Training LLMs to Reason and Leverage Search Engines with Reinforcement Learning (2025)**

Prompting a capable LLM to call a search engine mid-reasoning is not the same as training it to interact with search *optimally*. Search-R1 extends DeepSeek-R1-style outcome-reward RL so the policy LLM learns to autonomously interleave multi-turn search calls with step-by-step reasoning, using only a simple final-answer reward and masking retrieved tokens out of the RL loss for stability. Trained on Qwen2.5, this yields **24% relative improvement (7B)** and **20% (3B)** in exact match over RAG baselines, averaged across seven QA benchmarks spanning in-domain and out-of-domain multi-hop settings.

**Key mechanism**
- RL objective `max E[r(x,y)] - beta*KL(policy||reference)` where the policy generates `y` interleaved with real-time search-engine retrieval, i.e. `pi(.|x;R)`, not just `pi(.|x)`
- Loss masking for retrieved tokens: policy-gradient loss is computed only over LLM-generated tokens, excluding retrieved passage tokens from the rollout sequence, to avoid destabilizing optimization from content the model did not generate
- Implemented with both PPO (actor-critic, clipped surrogate) and GRPO (group-relative, critic-free, reward baseline from group statistics) as interchangeable RL backbones
- Outcome-based reward only (exact match against gold answer) - no process/step-level reward engineering
- Training corpus merges NQ and HotpotQA; retrieval uses the 2018 Wikipedia dump with an E5 dense retriever, 3 passages per query for all retrieval baselines (fair comparison)

**Main findings**
- Average EM across 7 QA datasets (NQ, TriviaQA, PopQA, HotpotQA, 2Wiki, Musique, Bamboogle): Search-R1-base (PPO) 0.431 on Qwen2.5-7B vs best non-RL baseline RAG 0.304 and rejection sampling 0.348
- 3B model: Search-R1-base (PPO) 0.303 average EM vs RAG 0.270, rejection sampling 0.265
- Search-R1 beats R1 (RL reasoning without any search, 0.276 on 7B) - retrieval access adds a further, separable gain on top of RL-trained reasoning alone
- PPO vs GRPO: GRPO converges faster early in training, but on the 7B-base model PPO reaches the higher final average EM (0.431 vs 0.350); on 3B-instruct GRPO edges PPO slightly (0.336 vs 0.325)
- Larger models exploit search better: the 7B model's gap over the next-best baseline is substantially larger than the 3B model's gap, indicating search-interaction skill itself scales with model size

**Key takeaways**
- Outcome-only reward, with retrieved-token loss masking, is sufficient to train a stable multi-turn search policy - no explicit process reward or step-level supervision is required to get large gains over prompted RAG
- The gain from RL-trained search interaction is additive to, not a substitute for, RL-trained reasoning: search access and reasoning quality are separately optimizable
- Base and instruction-tuned models both benefit, but the interaction between model scale and search-skill acquisition means small models see proportionally smaller gains from the same RL recipe

**Relevance**
- Core reference for R51 RL navigators: the retrieved-token loss-masking trick and the PPO/GRPO comparison are directly reusable if KGF trains a policy to decide when/how to traverse the graph or issue further retrieval calls during multi-hop answering
- The finding that outcome-only reward suffices (no process reward needed) is a useful prior against over-engineering a KGF traversal reward function before trying the simple baseline

**Tags**
- #ReinforcementLearning
- #SearchAgents
- #RAG
- #MultiHopQA
- #GRPO

**Source**
- Download: https://arxiv.org/abs/2503.09516
- Local: [paper] Search-R1 RL Search-Augmented LLMs, 2025.pdf
