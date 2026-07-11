**Graph Evolution: Densification and Shrinking Diameters, Leskovec, Kleinberg, Faloutsos, TKDD 2007 (arXiv physics/0603229)**

The empirical laws of GROWING real graphs, measured over time on 9 large evolving networks: edges grow superlinearly in nodes as a **densification power law e(t) ∝ n(t)^a with 1 < a < 2** (arXiv citations a = **1.68**, patent citations a = **1.66**, autonomous systems a = **1.18**, affiliation graphs a = 1.08-1.15, email a = 1.11-1.26), and **effective diameter SHRINKS** as the graph grows - both contradicting the constant-average-degree and slowly-growing-diameter assumptions of Erdos-Renyi-era models.

**Key mechanism**
- Densification exponent a: slope of log(edges) vs log(nodes) over the growth history; a = 1 means constant average degree, a = 2 means fully dense; real graphs sit consistently between
- Effective diameter: the 90th-percentile pairwise hop distance (robust to outliers); measured decreasing then stabilizing as each network grows
- Forest Fire generative model: new node picks an ambassador, "burns" recursively through its out- and in-links with forward probability p and backward ratio r; a narrow sweet spot of (p, r) reproduces BOTH densification (a = 1.21 realistic case) and shrinking diameter simultaneously
- Community Guided Attachment gives densification analytically: a = 2 − log_b(c) for difficulty constant c in [1, b)

**Main findings**
- Densification is intrinsic and stable per network - the exponent is a fingerprint of the growth process; a CHANGE in slope means the process changed
- Diameter shrinks because densification outpaces node arrival - new edges disproportionately close long ranges
- Gelation/missing-past effects checked and excluded - the laws are not artifacts of observation windows

**Key takeaways**
- For KGF: log E vs log N over the created_at-ordered ingest is a one-line instrument; a stable a with a breakpoint is a structural regime-change detector with published precedent
- The REG-1 forensics question "did the growth law break near doc 135-154" is exactly a densification-slope breakpoint test
- Effective diameter per document checkpoint is the companion series - a diameter that stops shrinking or reverses marks fragmentation onset

**Tags**: #DensificationPowerLaw #ShrinkingDiameter #GrowingGraphs #ForestFire #StructuralTimeSeries

**Source**: https://arxiv.org/abs/physics/0603229. Local: [paper] Graph Evolution Densification, 2006-03.pdf
