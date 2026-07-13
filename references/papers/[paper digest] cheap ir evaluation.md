# Cheap IR Evaluation: Fewer Topics, No Relevance Judgements, and Crowdsourced Assessments

**Author**: Kevin Roitero (Università degli Studi di Udine; PhD thesis, supervisor Stefano Mizzaro)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2011.00479

**Publication date**: 2020-11 (arXiv; PhD thesis)

## Summary

- Three-part thesis attacking the cost of building IR test collections from different angles: **fewer topics**, **no relevance judgements**, and **crowdsourced assessments**
- Part 1 gives an extensive empirical study of using fewer topics for retrieval evaluation, covering topic count, specific topic subsets, and the resulting statistical power tradeoff - the direct source of topic-subset sizing guidance
- Part 2 reproduces, extends, and generalizes state-of-the-art methods for evaluation **without relevance judgements**, including data-fusion and machine-learning combinations of those methods
- Part 3 uses crowdsourcing to gather relevance labels, studying the effect of fine-grained judgement scales and methods to transform judgements between different relevance scales
- Consolidates prior Roitero/Mizzaro conference work (topic-subset selection, judgement-free evaluation) into one coherent cost-reduction framework rather than introducing a single new headline result

**Relevance to Knowledge Graph Foundry**: the topic-subset sizing tradeoff (Part 1) is the direct precedent for KGF's frozen-but-larger probe manifest strategy - it quantifies how much statistical power is lost or retained as topic count shrinks, which is exactly the tradeoff KGF is navigating when deciding whether to freeze the benchmark at its current probe count or grow it. The no-relevance-judgement methods (Part 2) are a secondary lever if KGF ever needs to extend probe coverage without paying for new gold answers.

**Tags**: topic-subset-selection, cheap-evaluation, crowdsourcing, relevance-judgements, statistical-power, ir-test-collections

**Source**: https://arxiv.org/abs/2011.00479
