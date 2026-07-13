**CRITIC: LARGE LANGUAGE MODELS CAN SELF-CORRECT WITH TOOL-INTERACTIVE CRITIQUING (2024)**

CRITIC gives an LLM the ability to call external tools - a Python interpreter, a search API, a toxicity classifier - to check its own draft output, then revises the output using the tool's verdict rather than its own opinion. On mathematical program synthesis, tool-grounded correction lifts GSM8k accuracy by **up to +12.7 points** (LLaMA-2-70B oracle setting) and TabMWP by **up to +32.3 points**, and on toxicity reduction it more than halves average toxicity (0.325 to 0.173 for ChatGPT) while cutting perplexity.

**Key mechanism**
- Verify-then-correct loop: generate initial output, call a tool to evaluate a specific verifiable aspect (execution result, search evidence, toxicity score), then revise conditioned on the tool's feedback
- Up to n=4 correction iterations per instance, stopping early if two consecutive revisions leave the executed result unchanged
- Tool choice is task-specific: Python interpreter for math (execution errors and results as natural-language feedback), search engine for open-domain QA, learned classifier for toxicity
- Ablates "w/o Tool" (model critiques its own text with no external check) as a control condition against the full tool-grounded variant

**Main findings**
- Math program synthesis (GSM8k / SVAMP / TabMWP), ChatGPT: PoT baseline 72.5/82.0/75.0 to CRITIC 78.2/83.3/89.0 (+5.7/+1.3/+14.0); oracle-correction variant reaches 83.9/89.0/94.0
- Tool-interaction is the load-bearing component: removing the tool ("w/o Tool") drops gains to near-zero or negative (e.g., Text-Davinci-003 SVAMP -3.3 with tool vs -3.3 without - tool-free self-critique contributes marginally or hurts)
- Toxicity reduction: ChatGPT+CRITIC toxicity 0.325 to 0.173 (Max. Prob. metric) and perplexity 0.192 to 0.040, beating several dedicated detoxification baselines (PPO, Quark) while using only inference-time correction
- Free-form QA: CRITIC surpasses ReAct (search-only) by +5.1 to +8.2 F1 by combining the model's parametric knowledge with external verification rather than replacing it

**Key takeaways**
- The critical resource in a correction loop is the tool's feedback signal, not the number of refinement iterations - a model refining against its own untooled critique gains little to nothing
- Correction should stop when the tool-derived result stabilizes across iterations, not run a fixed budget
- The verify-then-correct pattern generalizes across task types (execution, retrieval, classification) as long as the tool call is cheap enough to run per-candidate at inference time

**Relevance**
- Directly informs the ingest-time repair loop: an external tool (schema validator, graph structural check, source-passage lookup) must hold the chunk and candidate graph state live during the verify-then-correct cycle, matching CRITIC's requirement that the tool call happen per-candidate, not as a post-hoc batch pass

**Tags**
- #SelfCorrection
- #ToolUse
- #VerifyThenCorrect

**Source**
- Download: https://arxiv.org/pdf/2305.11738
- Local: [paper] critic tool-interactive critiquing, 2024.pdf
