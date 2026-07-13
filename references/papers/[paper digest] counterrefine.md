**CounterRefine: Answer-Conditioned Counterevidence Retrieval for Inference-Time Knowledge Repair in Factual Question Answering**

CounterRefine is a lightweight repair layer for short-form RAG that treats the draft answer as a hypothesis to test, improving a matched one-pass RAG baseline by up to **5.8 correct-rate points** on the full SimpleQA benchmark while changing only **5.6%** of outputs in a full Claude trace (180 beneficial changes vs 8 harmful).

Key mechanism:
- Issues answer-conditioned expansion queries to retrieve candidate-specific counterevidence for the draft answer, rather than generic re-retrieval
- Applies a constrained KEEP-or-REVISE refinement step: the model may only keep the draft or propose a revision
- Proposed revisions are accepted only after deterministic validation, gating acceptance rather than trusting the model's self-assessment
- Deliberately narrow scope - adds one evidence-gathering pass plus one guarded refinement call, not a broad agentic re-generation loop

Main findings:
- Up to 5.8-point correct-rate gain over a matched one-pass RAG baseline on full SimpleQA
- Touches only 5.6% of outputs in the full Claude trace, with a 180:8 beneficial-to-harmful change ratio - most outputs are correctly left untouched
- Errors in factual QA are often failures of commitment (wrong answer chosen despite adequate retrieval), not failures of access

Key takeaways (relevance to KGF): the KEEP/REVISE gate with deterministic post-hoc validation is a conservative repair pattern that limits blast radius - only a narrow slice of outputs get touched, and validation prevents unsupported revisions from being accepted. This directly protects against alias-sprawl during KGF entity repair passes, where an unconstrained revise-everything approach risks introducing spurious new aliases; CounterRefine's answer-conditioned counterevidence retrieval also suggests targeting repair-time queries specifically at the existing entity/claim under test rather than broad re-retrieval.

Tags: keep-revise, self-correction, counterevidence-retrieval, inference-time-repair, factual-qa

Source: https://arxiv.org/abs/2603.16091
