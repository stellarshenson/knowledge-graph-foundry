# Speculative RAG - drafting with a small specialist, verifying with a large generalist

**arXiv 2407.08223 (2024, Google/UCSD, Wang et al.)**. Transfers the draft-verify pattern to RAG: a small instruction-tuned RAG DRAFTER generates multiple answer drafts (each with rationale) in parallel from clustered subsets of the retrieved documents (diverse-perspective partitions), and a large generalist RAG VERIFIER scores the drafts and picks the best - **+12.97% accuracy on PubHealth while reducing latency by 50.83%** versus conventional RAG with the large model alone.

**Key mechanism**: retrieval results are clustered by perspective; each draft conditions on ONE subset (cheap, parallel, diverse); the verifier never reads the full retrieval pool - it reads drafts + rationales, making verification much cheaper than generation over everything. The drafter requires no tuning of the verifier.

**Main findings**: parallel diverse speculation + selective verification beats monolithic processing on BOTH accuracy and latency across 4 QA benchmarks - speculation is not just an efficiency trade, the diversity of independent drafts is itself an accuracy lever; draft rationales are what make cheap verification possible.

**Key takeaways for KGF**: precedent that draft-verify wins in a KNOWLEDGE task, not just token decoding - and the accuracy gain came from diverse parallel hypotheses, which maps to KGF's multi-candidate speculation (multiple candidate pins per chunk, multiple bridge hypotheses per gap) adjudicated by one verifier pass. Drafts carrying rationales = speculative objects carrying provenance/justification, the property that makes lazy verification and audit possible (R36 justification records, H395 quarantine).

**Tags**: speculative-execution, rag, draft-verify, diverse-hypotheses
**Source**: https://arxiv.org/abs/2407.08223 (PDF: `[paper] Speculative RAG, 2024-07.pdf`)
