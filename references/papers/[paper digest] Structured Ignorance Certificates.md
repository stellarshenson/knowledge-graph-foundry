**Calibration of Structured Ignorance Certificates for Diagnosing Unknown Unknowns in Reasoning Models, Sahoo, arXiv 2606.08571, 2026**

Structured Ignorance Certificates (SICs) - a JSON schema that forces a model to name the missing domain intersection, enumerate required concepts, and propose a retrieval query instead of hallucinating - reach **99.46%** JSON validity and a mean Certificate Specificity Score of **0.967** on 735 held-out cross-domain questions, fine-tuned on a **7,347**-sample Unknown-Unknown (UU) dataset spanning seven domains.

**Key mechanism**
- SIC output schema demands three fields on refusal: the missing domain intersection, the concepts required to answer, and a productive retrieval query - replacing free-text hedging with structured epistemic metadata
- UU dataset construction: Qwen3-14B stitches together questions from seven single-domain sources (physics, biology, engineering, CS, economics, medical, legal) into cross-domain queries no single-domain expert could answer
- A 14B model is fine-tuned with GRPO (Group Relative Policy Optimization) using a composite reward blending retrieval utility, concept specificity, and output-format validity
- A paraphrase-divergence probe trained on model responses independently confirms SIC-tuned outputs carry a higher unknown-unknown signal than the base model's free-text refusals

**Main findings**
- 99.46% JSON validity rate on held-out cross-domain questions - the schema constraint is learnable and near-fully reliable
- 3.6% ROUGE-L improvement over the base model on retrieval-grounded generation when the SIC's proposed query is used to fetch supporting context
- Explicit epistemic structuring (naming what's missing, not just refusing) is a measurable, trainable capability distinct from plain abstention

**Key takeaways**
- The three-field SIC schema (missing domain, required concepts, unlock query) is a direct template for the gap-ledger record: it separates "why this is unanswerable" from "what would resolve it," which the ledger currently expresses only informally
- The GRPO composite reward (retrieval utility + specificity + format validity) is a reusable recipe if the gap-ledger record schema is ever trained rather than prompted
- Cross-domain question stitching is a cheap way to generate hard-negative "should abstain" training examples for a KGF abstention classifier

**Tags**: #Abstention #EpistemicUncertainty #StructuredOutput #GRPO #UnknownUnknowns

**Source**: https://arxiv.org/abs/2606.08571. Local: [paper] structured ignorance certificates, 2026.pdf
