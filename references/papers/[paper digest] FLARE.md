**FLARE: Active Retrieval Augmented Generation, Jiang, Xu, Gao, Sun, Liu, Dwivedi-Yu, Yang, Callan, Neubig, EMNLP 2023 (arXiv 2305.06983)**

The confidence-threshold pole of adaptive retrieval. Instead of retrieving once up front, FLARE generates a temporary next sentence, and if ANY token in it falls below a probability threshold θ, uses that sentence as a retrieval query and regenerates. Tested on **4** long-form knowledge-intensive tasks (2WikiMultihopQA, ASQA, StrategyQA, WikiAsp), superior or competitive on all against single-retrieval and passive multi-retrieval baselines.

**Key mechanism**
- Forward-looking trigger: generate tentative sentence s-hat, retrieve iff min token probability < θ (θ=0 never retrieves, θ=1 retrieves every sentence)
- Grounding: LMs are reasonably calibrated - low token probability correlates with missing knowledge (Kadavath 2022), so the model's own uncertainty IS the sufficiency signal
- Query formation: either mask low-confidence tokens below β (implicit query) or generate explicit questions targeting the low-confidence spans
- No training - works on frozen LMs via the token-probability API

**Main findings**
- Active (when-needed) retrieval beats retrieve-once and beats fixed-interval retrieval on long-form tasks
- Anticipating FUTURE content (forward-looking query) beats using the last generated sentence as query
- The confidence threshold is the calibration knob: retrieval frequency tunes smoothly against quality

**Main limitation**: needs token logprobs; each trigger costs a regeneration pass - the sentence is generated twice on escalation.

**Key takeaways**
- A FREE, untrained sufficiency signal (model confidence) demonstrably separates need from no-need at sentence granularity
- Directly analogous to KGF-H382's threshold arm: a scalar signal + calibrated threshold gating context escalation
- The regenerate-on-trigger cost profile matches H382's ladder economics - escalation must be rare to pay

**Tags**: #FLARE #ActiveRetrieval #ConfidenceThreshold #AdaptiveRAG #EMNLP

**Source**: https://arxiv.org/abs/2305.06983. Local: [paper] FLARE active retrieval, 2023-05.pdf
