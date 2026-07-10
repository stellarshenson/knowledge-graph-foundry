# [paper digest] A Framework for Intelligence and Cortical Function Based on Grid Cells in the Neocortex

**A Framework for Intelligence and Cortical Function Based on Grid Cells in the Neocortex** (Hawkins, Lewis, Klukas, Purdy, Ahmad, *Frontiers in Neural Circuits*, 2019). The theoretical companion to *A Thousand Brains* (2021). Central claim: **every** cortical column learns complete models of objects by storing sensory features at **locations** in object-anchored reference frames built from grid-cell-like codes; **thousands** of columns each model the same object from partial evidence and reach a percept by **lateral voting**. Mechanistic but largely **UNVERIFIED** as an engineering system - the framework is a neuroscience hypothesis with limited quantitative benchmarks at publication.

## Key mechanism
- **Reference frames** - each column pairs a sensory feature with a location code (grid-cell modules) relative to the object, not the body; a column stores an object as a set of (feature, location) pairs, i.e. a coordinate-indexed model
- **Sensorimotor prediction** - as sensors move, the column predicts the next feature at the next location; correct prediction confirms the object hypothesis, mismatch signals a new object or error
- **Thousand-brains voting** - many columns each hold a partial, independent model of the same object; long-range lateral connections let columns exchange their current object+pose hypotheses and converge on a consensus (the percept) quickly, even when each column saw only a fragment
- **Uniform cortical algorithm** - the same column circuit is proposed for vision, touch, and (speculatively) abstract concepts, where "location" generalizes to positions in an abstract conceptual space

## Main findings
- A location-based framework unifies grid/place-cell neuroscience with a repeating cortical-column computation
- Voting explains fast, robust recognition from ambiguous partial input - a majority of independent views agreeing is far more reliable than any single view
- Extends naturally from physical objects to structured knowledge if concepts can be assigned reference-frame coordinates (this extension is speculative)

## Key takeaways
- The transferable ideas: (1) many independent partial models of one entity, (2) a voting/consensus step over those models, (3) knowledge stored as features indexed by position in a reference frame
- Honest status: the voting and reference-frame claims are neuroscience theory; Numenta's later Thousand Brains Project (Monty, 2024-2025) is the engineering realization and is early-stage, not a benchmarked competitor to deep learning
- For a retrieval system the operational residue is the voting pattern (ensemble of independent retrieval views) and content indexed by structured keys, not the biological grid-cell detail

## Tags
`thousand-brains` `reference-frames` `voting` `cortical-columns` `sensorimotor` `numenta` `hawkins` `unverified-as-engineering`

## Source
- https://www.frontiersin.org/journals/neural-circuits/articles/10.3389/fncir.2018.00121/full
- PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC6336927/
