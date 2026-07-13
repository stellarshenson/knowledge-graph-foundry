**Safer or Luckier? LLMs as Safety Evaluators Are Not Robust to Artifacts, Chen, Goldfarb-Tarrant, arXiv 2503.09347, 2025**

Across **11** LLM judge models, apologetic-language artifacts alone can skew which content source is judged "safer" by up to **98%** - a distortion large enough to flip a comparative verdict independent of actual content safety. The study evaluates self-consistency in repeated judging, alignment with human judgments, and susceptibility to superficial phrasing artifacts (apologetic tone, verbosity).

**Key mechanism**
- Judge models are tested for self-consistency (same input judged repeatedly), human alignment, and sensitivity to non-substantive input artifacts
- Jury-based evaluation (aggregating verdicts from multiple judge models) is tested as a mitigation
- Artifact sensitivity is measured independent of model scale to isolate whether size predicts robustness

**Main findings**
- Larger models are not consistently more robust to artifacts; some smaller models resist specific artifacts better
- Jury aggregation improves both robustness and human-alignment but does not eliminate artifact sensitivity even in the best jury configuration
- Self-consistency failures compound with artifact sensitivity, so a single judge call is doubly unreliable for close calls

**Key takeaways**
- Confirms the same failure mode as the agentic-evals paper from the judge-design side: surface phrasing, not just decoding temperature, drives vote flips - the two variance sources are additive when estimating a "1% flip floor" per bench rung
- Motivates jury-of-judges over single-judge scoring where KGF verdicts are close to a threshold, and cautions that jury aggregation reduces but does not remove artifact-driven bias

**Tags**: #LLMJudge #ArtifactBias #JuryEvaluation #SafetyEvals #Robustness

**Source**: https://arxiv.org/abs/2503.09347. Local: [paper] safer or luckier llm safety evaluators, 2025.pdf
