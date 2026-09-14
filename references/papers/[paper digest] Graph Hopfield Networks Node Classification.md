**Graph Hopfield Networks: Energy-Based Node Classification with Associative Memory, Rao, Wa, Athavale, New Frontiers in Associative Memory workshop, ICLR 2026 (arXiv 2603.03464)**

The only published attempt to couple Hopfield retrieval to graph structure inside one energy - and a clean measurement of how little the memory contributes. GHN's energy adds a modern Hopfield retrieval term to a graph-Laplacian smoothing term; gradient descent on the joint energy interleaves Hopfield retrieval with Laplacian propagation.

**Key mechanism**
- `E_GH(X)` = Hopfield associative-memory energy + λ · graph Laplacian smoothing; λ ≤ 0 gives graph **sharpening** for heterophilous graphs without architecture changes
- Iterative energy descent replaces a stacked message-passing network

**Main findings**
- Memory retrieval gives **up to 2.0 pp on sparse citation networks** and up to 5 pp additional robustness under feature masking
- **The memory-disabled NoMem ablation already outperforms standard baselines on Amazon co-purchase graphs** - the authors attribute the bulk of the gain to the iterative energy-descent architecture as an inductive bias, not to the associative memory
- Benefits are explicitly described as **regime-dependent**

**Key takeaways**
- The strongest published null for adding a Hopfield layer to a graph pipeline: the memory term is worth ~2 pp and the architecture around it is worth more
- Confirms that "associative memory over node features" and "propagation over graph structure" remain two separate terms; the joint energy does not let content-based retrieval reach across structure it cannot see
- Workshop-scale evidence on citation and co-purchase graphs, not retrieval benchmarks

**Tags**: #GraphHopfield #NodeClassification #NullResult #EnergyBased #R59

**Source**: https://arxiv.org/abs/2603.03464. Local: [paper] Graph Hopfield Networks Node Classification, 2026.pdf
