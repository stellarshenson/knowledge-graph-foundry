**Bose-Einstein Condensation in Complex Networks, Bianconi, Barabasi, PRL 2001 (arXiv cond-mat/0011224)**

The hub-condensation phase transition in growing networks: map fitness-based preferential attachment (attach probability ∝ fitness eta_i × degree k_i) onto a Bose gas (fitness → energy, edges → particles); the network then has **three thermodynamic phases** - (a) scale-free (all fitnesses equal), (b) **fit-get-rich** (degree grows as k(t) ∝ t^{f(eta)/C}, fitter nodes grow faster but no single winner), and (c) **Bose-Einstein condensate: the single fittest node captures a FINITE fraction of all edges independent of network size** - "winner-takes-all" as a genuine phase transition, not a matter of degree.

**Key mechanism**
- Condensation condition: when the fitness distribution rho(eta) makes the chemical-potential equation unsolvable (no mu satisfies mass conservation), the excess mass condenses onto the lowest-energy (highest-fitness) node
- The transition depends only on the SHAPE of rho(eta) - some fitness distributions can never condense, others always do; a changing fitness distribution during growth can cross the boundary
- Below condensation the degree distribution stays power-law with fitness-dependent exponents; above it the largest hub decouples from the distribution

**Main findings**
- First-mover advantage is a phase, not a constant: in the scale-free phase oldest nodes win; in fit-get-rich, late high-fitness arrivals overtake; in condensation, one node runs away
- The largest hub's edge SHARE (k_max / E) is the order parameter - flat share = healthy, growing share = approaching condensation

**Key takeaways**
- For KGF ingest forensics: track k_max/E and top-decile degree share per document; a rising share as the pile grows is the published signature of hub condensation - the structural regime where one entity (a country, a profession like "film director", a date) starts absorbing all new attachment
- Wikipedia-corpus entities have wildly heterogeneous "fitness" (mention frequency); a comparison-question corpus adds shared-attribute hubs (country nodes) exactly of the condensing class - relevant to REG-1 where retrieval surfaces films but not their directors
- A condensing hub degrades retrieval two ways: it crowds render budgets and it collapses embedding neighborhoods around generic entities

**Tags**: #HubCondensation #PhaseTransition #PreferentialAttachment #FitnessModel #GrowingGraphs

**Source**: https://arxiv.org/abs/cond-mat/0011224. Local: [paper] Bose-Einstein Condensation in Networks, 2000-11.pdf
