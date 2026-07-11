**The Dynamics of Correlated Novelties, Tria, Loreto, Servedio, Strogatz, Scientific Reports 2014 (arXiv 1310.1953)**

The generative theory behind Heaps' law: a **Polya urn with triggering** ("expanding adjacent possible") in which each novelty makes further related novelties reachable, reproduces SIMULTANEOUSLY **Heaps' law D(N) ∝ N^beta (beta < 1)** and **Zipf's law f(R) ∝ R^-alpha with beta = 1/alpha**, plus the empirical signature that novelties arrive in correlated CLUSTERS, not as independent events - verified on Wikipedia edits, Last.fm listening, Gutenberg texts, del.icio.us tags.

**Key mechanism**
- Urn: draw an element; reinforce it with rho copies (Zipf side); if it is NEW, add nu+1 fresh adjacent elements (Heaps side - the adjacent possible expands)
- Heaps exponent beta = nu/rho when nu < rho (sublinear regime); the exponent is a RATIO of exploration to reinforcement rates
- Semantic correlations: one novelty raises the short-term probability of related novelties - measurable as clustering of first-appearance events far above a randomized-order null

**Main findings**
- Heaps and Zipf emerge from ONE process - a deviation in one law without the other indicates the process changed, not just the rate
- The randomized-null test (shuffle event order, compare novelty-interval statistics) is the paper's key instrument for detecting correlated novelty bursts

**Key takeaways**
- Grounds KGF's H47 Heaps marker (b = 0.771/0.803) in a mechanism: the exponent is exploration/reinforcement ratio; a Heaps BREAK during ingest means the corpus regime changed (new topic cluster entered) or resolution failed (reinforcement misrouted to fresh nodes)
- The per-document novelty series (new entities per doc, new TYPES per doc - KGF's 97 labels) with the shuffle-null test detects topic-cluster arrival - exactly the class of event that could precede REG-1 (a burst of same-schema film/director entities crowding one embedding region)
- Type-token curves per label class (new PERSON entities vs new WORK entities) localize WHICH vocabulary broke its growth law at the regression boundary

**Tags**: #HeapsLaw #ZipfLaw #PolyaUrn #AdjacentPossible #NoveltyDynamics

**Source**: https://arxiv.org/abs/1310.1953. Local: [paper] Dynamics of Correlated Novelties, 2013-10.pdf
