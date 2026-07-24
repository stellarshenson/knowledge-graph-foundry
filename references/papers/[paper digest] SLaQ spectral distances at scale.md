**Just SLaQ When You Approximate: Accurate Spectral Distances for Web-Scale Graphs (2020)**

A pure **computational** contribution: how to compute spectral graph distances (NetLSD's heat trace, VNGE's von Neumann entropy) on graphs with **billions** of nodes and edges. SLaQ applies stochastic Lanczos quadrature to approximate the spectral densities in time **linear in |E|**, with derived error bounds, beating prior approximations "oftentimes by several orders of magnitude in approximation accuracy" and comparing million-scale graphs in minutes on one machine.

**Key mechanism**
- Spectral descriptors are traces of matrix functions, `tr f(L) = Σ_j f(λ_j)` - computing them exactly needs the full eigendecomposition, which is cubic
- Stochastic Lanczos quadrature (SLQ) estimates `tr f(L)` via Hutchinson's stochastic trace estimator plus a Gauss quadrature rule derived from a short Lanczos run, requiring only matrix-vector products
- Error bounds are derived for the specific descriptors (heat kernel trace for NetLSD, von Neumann graph entropy for VNGE) rather than assumed
- Prior practice (Taylor expansion, eigenvalue interpolation) is shown to carry weak or absent guarantees

**Main findings**
- Orders-of-magnitude better approximation accuracy than incumbent approximations at comparable runtime
- Linear-in-|E| scaling makes billion-edge spectral comparison tractable
- Implementation released in the google-research repository

**Key takeaways**
- The accuracy of a spectral descriptor at scale is dominated by the approximation scheme, not by the descriptor's definition - a point that matters whenever spectral results at scale disagree with small-graph results
- SLQ is the right tool for any trace-of-matrix-function estimate on a large sparse graph

**Relevance**
- **Fenced on V4 (wrong scale), not on evidence.** SLaQ solves a problem KGF does not have: our medium graph is 6,626 nodes, where R52-H598 ran exact `scipy.eigsh` and even the exact matrix exponential `expm` in seconds. There is no approximation error to remove
- The descriptors it accelerates (heat trace, von Neumann entropy) are both independently killed on our substrate - R52-H598 for the heat kernel, R43-H487 which found von Neumann graph entropy BLIND
- Filed so that a future scale rung (large, or the public-benchmark corpora) has the recipe on hand if a spectral instrument ever earns its place; today it accelerates a computation we have no reason to run

**Tags**
- #SpectralGraphTheory
- #Approximation
- #Scalability
- #LanczosQuadrature

**Source**
- Download: https://arxiv.org/abs/2003.01282
- Local: [paper] SLaQ spectral distances at scale, 2020.pdf
