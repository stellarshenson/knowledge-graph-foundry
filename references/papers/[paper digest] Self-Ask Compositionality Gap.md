# Measuring and Narrowing the Compositionality Gap in Language Models

**Authors**: Ofir Press, Muru Zhang, Sewon Min, Ludwig Schmidt, Noah A. Smith, Mike Lewis

**arXiv link (source for re-download)**: https://arxiv.org/abs/2210.03350

**Publication date**: 2022-10-07 (v1); v3 2023-10-17

## Summary

- Defines the compositionality gap: the fraction of 2-hop questions a model answers wrong despite answering both constituent sub-questions correctly
- On the new Compositional Celebrities (CC) dataset (8.6k 2-hop questions across 17 templates), GPT-3 davinci-002 answers 45.4% of 2-hop questions correctly overall, reaching 84.6% on the easiest category (Birthplace/Domain Name) and only 1.2% on the hardest (Birth Year/Literature Nobel Prize Winner) despite 80% sub-question accuracy on that hardest category
- Compositionality gap holds at roughly 40% across GPT-3 model sizes (Ada 0.35B to Davinci 175B) and does not shrink with scale, for both base and InstructGPT model families; ChatGPT and GPT-4 show gaps of 42.9% and 23.0% respectively (caveat: CC may have leaked into GPT-4's training data)
- Model confidence (low perplexity on sub-question answers) correlates with compositional success: 81.1% correct on the compositional question when max sub-answer perplexity is 1.000-1.002, versus 42.6% when perplexity is 1.232-6.738
- Self-ask prompting (explicit "Are follow up questions needed here" / "Follow up:" / "Intermediate answer:" scaffolding) beats chain-of-thought on Bamboogle (their hand-built 125-question 2-hop set): 57.6% vs 46.4% accuracy, an 11-point absolute gain, with smaller gains on 2WikiMultiHopQA (30.0% vs 29.8%) and Musique (13.8% vs 12.6%), all measured on Davinci-002
- Self-ask + Search Engine integration lifts accuracy further: 60.0% on Bamboogle, 40.1% on 2WikiMultiHopQA (up from 30.0%), 15.2% on Musique - the largest jump (10 points absolute) on 2WikiMultiHopQA
- Direct prompting and a bare search engine baseline underperform badly: search engine alone scores 0.0% on Bamboogle, 2.2% on 2WikiMultiHopQA, 1.5% on Musique (Bamboogle was explicitly filtered to exclude questions a popular search engine could answer directly)
- Self-ask matches or beats Least-to-Most prompting (Zhou et al. 2022) while running over 30% faster and using fewer output tokens (569 vs 844 on 2WikiMultiHopQA, 663 vs 1020 on Musique) because it decomposes and answers sub-questions in a single forward pass with one prompt, versus Least-to-Most's multiple prompt passes
- Self-ask also produces cleaner parseable final answers: only 3% of self-ask+search outputs failed to match the expected short-answer format, versus 17% for self-ask alone and 40% for chain-of-thought on Bamboogle

**Key mechanism**: Self-ask's rigid "Follow up:" / "Intermediate answer:" scaffold cleanly demarcates each sub-question's start and end within a single autoregressive generation, which both disentangles question decomposition from sub-answer generation (improving accuracy on novel, varied questions) and lets an external tool - a search engine API - be substituted transparently as the sub-question answerer, since the LM's own turn is simply paused, the retrieved text spliced into the prompt as if the model had generated it, and generation resumed with no fine-tuning or architecture change required.

**Relevance to Knowledge Graph Foundry**: Self-ask's tool-substitution pattern (freeze generation at "Follow up:", inject retrieved evidence, resume) is a template for grounding KGF's multi-hop question answering in the Neo4j graph rather than parametric recall - each follow-up could route to PPR-seeded retrieval (dense@16=0.854) instead of a web search API, giving H382's context-escalation gate a natural per-hop decomposition boundary; the paper's finding that decomposition quality (not model scale) drives multi-hop accuracy also supports R48's community-segmentation work as a lever on context assembly rather than raw retrieval volume.
