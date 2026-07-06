# The Extractive-Abstractive Spectrum: Uncovering Verifiability Trade-offs in LLM Generations

**Source**: https://arxiv.org/abs/2411.17375
**Authors**: Theodora Worledge, Tatsunori Hashimoto, Carlos Guestrin
**Venue/Date**: Stanford preprint, November 2024

## Summary

The paper frames search engines and LLMs as endpoints of an "extractive-abstractive spectrum" and studies how verifiability trades off against utility across five intermediate operating points. Human evaluations on seven systems and four query distributions show that as outputs become more abstractive, perceived utility rises by up to 200% while proper citation drops by up to 50% and verification takes up to 3x longer.

## Method

- Defines five operating points from extractive to abstractive - snippets, quoted, entailed, paraphrased, and full abstractive synthesis
- Extractive outputs return verbatim source snippets with links; abstractive outputs synthesize across sources without reliable citation
- Human evaluation across web search, language simplification, multi-step reasoning, and medical advice queries
- Measures perceived utility, proportion of properly cited sentences, and time to verify cited information
- Survey of real users on when they prefer search engines versus LLMs for high-stakes queries

## Key Findings

- Perceived utility improves by as much as 200% moving toward abstraction
- Proportion of properly cited sentences decreases by up to 50%
- Users take up to 3x longer to verify citations in more abstractive outputs
- Cites prior work: only 74.5% of deployed-system citations accurate, 51.5% of citation-needing sentences actually cited
- Users prefer search engines for high-stakes queries where provenance matters

## Relevance to KGF

- SUPPORTS H27 (hollow graph): the paper's central finding is that verbatim, extractive content with source spans is far more verifiable than paraphrased synthesis - the exact rationale for storing verbatim provenance spans and NO paraphrased propositions
- Warns that abstractive paraphrase is where citation quality collapses, reinforcing that a KGF audit loop should ground claims to verbatim spans rather than trust generated propositions
- The verify-time cost curve motivates retrieval-first design: cheaper verification when evidence is stored as directly-citable spans
