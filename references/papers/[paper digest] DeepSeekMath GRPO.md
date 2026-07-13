**DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models (2024)**

The paper trains a 7B open model to competition-math strength through a two-part recipe: a 120B-token web-mined math pretraining corpus, and a lightweight RL algorithm - Group Relative Policy Optimization (GRPO) - that drops PPO's separate value/critic network entirely. DeepSeekMath-RL 7B reaches **51.7% on the competition-level MATH benchmark** and **88.2% on GSM8K** without external tools or majority voting, approaching Gemini-Ultra and GPT-4 while using a model 77x smaller than Minerva 540B. The result most relevant to a scorer-distillation context: RL post-training on a small model, without any new labeled data, buys 4-5 points of accuracy at near-zero added parameter cost.

**Key mechanism**
- GRPO forgoes the critic model; for each question it samples a group of G outputs from the old policy, scores them with a reward model, then normalizes rewards within the group (subtract mean, divide by std) to form the advantage - this group-relative baseline replaces GAE/value-function estimation entirely
- The GRPO objective adds the KL-divergence term directly to the loss (not folded into the per-token reward as in PPO), using an unbiased, always-positive KL estimator: `KL = π_ref/π_θ − log(π_ref/π_θ) − 1`
- Two supervision granularities: outcome supervision (one normalized reward per full output, broadcast to every token) and process supervision (a normalized reward per reasoning step, summed forward from each token)
- Iterative GRPO closes the loop: after each RL iteration the reward model is retrained on a replay mix of 10% historical + fresh policy-sampled data, and the reference model is reset to the current policy - this keeps the reward signal from going stale as the policy improves
- A unified gradient-coefficient view (Eq. 5) shows SFT, RFT, DPO, PPO, and GRPO are all the same gradient template with a different (data source, reward function, gradient coefficient) triple - useful as a design checklist when picking a distillation/RL scheme

**Main findings**
- GRPO lifts DeepSeekMath-Instruct 7B from 82.9%→88.2% (GSM8K) and 46.8%→51.7% (MATH), plus out-of-domain gains (CMATH 84.6%→88.8%) despite training only on GSM8K/MATH-domain instruction data
- Online sampling beats offline: Online RFT clearly outperforms offline RFT, and the gap widens as training progresses (policy drifts further from the frozen SFT model)
- GRPO beats Online RFT specifically because of its signed, magnitude-aware gradient coefficient - RFT only reinforces correct answers uniformly and never penalizes incorrect ones; GRPO does both, differentially
- Process supervision (GRPO+PS) beats outcome supervision (GRPO+OS), confirming step-level reward signal is worth the added labeling complexity
- Iterative RL (refreshing the reward model each round) delivers a further jump, largest at the first iteration (Figure 6: ~83%→89% GSM8K over 3 iterations)
- Data-quality ablation: a domain-filtered 120B-token web corpus beats a general web corpus of similar or larger size by a wide margin (23.8% vs 2.9% zero-shot GSM8K under identical training budget) - corpus curation dominates raw scale
- Negative result: training on raw arXiv papers gave no improvement or outright degradation on every math benchmark tested, contradicting the common assumption that arXiv math text helps math reasoning

**Key takeaways**
- A critic-free RL algorithm cuts training memory/compute roughly in half relative to PPO while matching or beating it - directly relevant to any plan to RL-tune a small scorer/judge/navigator model under a constrained GPU budget
- Group-relative advantage estimation only needs multiple samples per prompt and a reward model - no separate value network to train or store, which lowers the bar for standing up an RL loop at all
- The online-vs-offline and outcome-vs-process ablations generalize beyond math: for any small-model RL/distillation setup, sampling from the live policy and rewarding at the finest granularity available both help, and both are cheap knobs to turn before reaching for a bigger model
- The negative arXiv-corpus result is a caution against assuming "more domain-adjacent text = better corpus" without measuring it directly

**Relevance**
- GRPO is the direct RL-navigator mechanism candidate for R51's "RL navigators" workstream - a critic-free, group-normalized advantage is cheap enough to run against a small scorer model without standing up a second value network
- The unified-paradigm table (Table 10) is a useful design template for choosing between SFT/RFT/DPO/PPO/GRPO when scoping a small-model scorer distillation approach

**Tags**
- #ReinforcementLearning
- #GRPO
- #SmallModelDistillation
- #LLMTraining

**Source**
- Download: https://arxiv.org/abs/2402.03300
- Local: [paper] DeepSeekMath GRPO, 2024.pdf
