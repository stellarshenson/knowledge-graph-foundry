**On Randomness in Agentic Evals, Bjarnason, Silva, Monperrus, arXiv 2602.07150, 2026**

Single-run pass@1 on SWE-Bench-Verified varies by **2.2 to 6.0 percentage points** depending on which run is selected, with standard deviations exceeding **1.5 points even at temperature 0** - collected from **60,000** agentic trajectories across three models and two scaffolds. The paper argues that reported 2-3 point improvements in agentic-eval leaderboards may reflect run-selection noise, not genuine progress.

**Key mechanism**
- Trajectories diverge early - often within the first few percent of generated tokens - and small token-level differences cascade into different tool calls and solution strategies
- Temperature 0 does not guarantee determinism in agentic loops: nondeterministic kernels, batching effects, and tool-call timing reintroduce variance even at greedy decoding
- Proposes pass@k (optimistic) and pass^k (pessimistic) with k>1 as a fuller performance envelope than single-shot pass@1

**Main findings**
- Single-run pass@1 estimates are unreliable at the scale most agentic papers report improvements
- Statistical power analysis is needed to size the number of runs required to detect a claimed effect
- Multiple independent runs per task are recommended as a minimum evaluation practice, especially for small deltas

**Key takeaways**
- Temp-0 non-reproducibility is real and material to KGF's LLM-as-judge scoring; before trusting a small per-rung metric delta, check whether it exceeds the observed vote-flip floor rather than assuming greedy decoding pins the answer
- Reinforces running judge votes as a repeated-sample statistic (n>1) rather than a single call, and sizing n against the effect being measured

**Tags**: #LLMJudge #Reproducibility #AgenticEvals #Variance #PassAtK

**Source**: https://arxiv.org/abs/2602.07150. Local: [paper] randomness in agentic evals, 2026.pdf
