**Error and Attack Tolerance of Complex Networks, Albert, Jeong, Barabasi, Nature 2000 (arXiv cond-mat/0008064)**

The canonical robustness result: scale-free networks are **extremely tolerant of random node failure** (diameter essentially unchanged with up to **5%** of nodes randomly removed) but **catastrophically fragile to targeted hub removal** (diameter **doubles when the top ~5%** most-connected nodes are removed), while exponential (Erdos-Renyi-class) networks degrade identically under both - robustness is a property of the degree distribution's heavy tail.

**Key mechanism**
- Random failure overwhelmingly hits low-degree periphery (the majority), which carries few paths; hubs carry the connectivity
- Targeted attack removes exactly the path-carrying nodes; the giant component fragments rapidly - largest-cluster fraction S collapses and mean isolated-fragment size <s> peaks around ~2 at the fragmentation threshold f_c (percolation-style transition)
- Measured on real WWW (325k nodes) and Internet AS maps plus model networks

**Main findings**
- S(f) and <s>(f) curves are the standard fragmentation instruments: S = giant-component share, <s> = mean size of the non-giant fragments; <s> peaking is the transition signature
- The SAME graph can be simultaneously robust and fragile - which one you observe depends on which nodes the perturbation touches

**Key takeaways**
- Inverted for KGF forensics: ingest is node ADDITION, and merge errors / fragment splits are effectively node removal/duplication on the connectivity backbone; the S and <s> series over the created_at replay are cheap phase instruments (KGF R09-H63 measured a static 72.8% lit share - the dynamic series is the missing instrument)
- A bad Bayesian merge on a hub is a targeted attack in reverse: it rewires many paths at once - hub-touching merges deserve a per-document audit line (KGF H91 lineage)
- The <s> ~ 2 peak signature gives a falsifiable prediction shape for the REG-1 window: if the graph crossed a fragmentation threshold, small-component mean size peaks near the regression boundary

**Tags**: #NetworkRobustness #GiantComponent #Fragmentation #ScaleFree #Percolation

**Source**: https://arxiv.org/abs/cond-mat/0008064. Local: [paper] Error and Attack Tolerance, 2000-08.pdf
