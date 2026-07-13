**Large Language Models Cannot Self-Correct Reasoning Yet (2023 / ICLR 2024)**

Testing GPT-3.5, GPT-4, GPT-4-Turbo, and Llama-2-70B on GSM8K, CommonSenseQA, and HotpotQA, the paper isolates "intrinsic self-correction" - a model correcting its own reasoning with no external feedback or oracle label - and finds accuracy **drops after self-correction on every model and every benchmark tested**: GPT-3.5 on CommonSenseQA falls from 75.8% to 41.8% after two self-correction rounds, and even GPT-4 on GSM8K drops from 95.5% to 89.0%.

**Key mechanism**
- Defines intrinsic self-correction precisely: the model reviews and revises its own prior answer using only its own judgment, with no ground-truth label and no external tool or verifier in the loop
- Three-step prompting identical in spirit to Self-Refine: (1) initial answer, (2) self-review and feedback, (3) revised answer, repeated for up to two rounds
- Runs a controlled contrast: "Self-Correct (Oracle)" uses the ground-truth label to decide whether to stop correcting (an upper-bound, not a deployable setting) versus "intrinsic" self-correction where the model alone decides when to stop
- Tests multiple self-correction prompt variants to rule out prompt design as the failure cause

**Main findings**
- With oracle labels (upper bound, not realistic): GPT-3.5 GSM8K 75.9% -> 84.3%, CommonSenseQA 75.8% -> 89.7%, HotpotQA 26.0% -> 29.0%; GPT-4 shows smaller but still positive oracle-guided gains
- Without oracle labels (intrinsic, the realistic setting): GPT-3.5 GSM8K drops 75.9% -> 74.7%, CommonSenseQA drops 75.8% -> 41.8%, HotpotQA drops slightly 26.0% -> 25.0%, all while consuming 3-5x more model calls
- GPT-4 shows the same directional pattern at smaller magnitude: GSM8K 95.5% -> 89.0%, CommonSenseQA 82.0% -> 80.0% (near flat), HotpotQA 49.0% -> 43.0%, after two self-correction rounds
- The oracle-vs-intrinsic gap is the whole story: prior papers reporting self-correction gains (Kim et al. 2023, Shinn et al. 2023) used oracle labels to decide when to stop, which silently supplies the external signal the model itself cannot generate

**Key takeaways**
- The core failure mode is not that self-correction prompting is badly engineered - additional prompt variants tested still fail to recover the losses - it is that the model has no reliable internal signal for "my answer is actually wrong," so it revises correct answers into incorrect ones as often as it fixes real mistakes
- Reported self-correction success in prior literature is largely an artifact of oracle-label stopping criteria, not genuine intrinsic capability
- More model calls (3-5x) under intrinsic self-correction produce worse accuracy, not better - the extra compute is actively harmful without a real external check

**Relevance**
- This is the direct threat model the grounded-critique ablation (H563) exists to test: an ungrounded self-critique pass on KGF's own extraction/answer output risks the same silent degradation shown here (CommonSenseQA -34 pp) unless the critique step is anchored to external, checkable evidence rather than the model's own unaided judgment
- Reinforces the Self-Refine finding from the other digest in this round - gains concentrate where the critic has real signal; this paper shows the failure side of that same coin when the critic has none
- Practical design implication for KGF: any self-repair loop needs an oracle-equivalent (source-grounded check, schema constraint, cross-reference) standing in for the missing ground truth, not model self-assessment alone

**Tags**
#SelfCorrection #LLMReasoning #GroundedCritique #ICLR2024

**Source**
- Download: https://arxiv.org/pdf/2310.01798
- Local: [paper] llms cannot self-correct reasoning, 2023.pdf
