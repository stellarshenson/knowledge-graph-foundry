**Laplacian Change Point Detection for Dynamic Graphs (LAD), Huang, Hitti, Rabusseau, Rabbany, KDD 2020 (arXiv 2007.01229)**

Change-point detection on a SEQUENCE of graph snapshots via the **Laplacian singular spectrum**: embed each snapshot as its top-k singular values of the (unnormalized) Laplacian, compare against short-term AND long-term sliding-window behavior, flag when the current spectrum deviates. The first method to explicitly separate short-term events from long-term regime changes in dynamic graphs.

**Key mechanism**
- Per snapshot: sigma vector = top-k singular values of L_t via truncated sparse SVD (k << n; low-rank captures dominant structure; node-permutation invariant; number of zero singular values tracks component count)
- Context matrix C from the previous l spectra (window); normal-behavior vector = top LEFT singular vector of C (the "typical spectrum" direction)
- Anomaly score Z = 1 − cos(sigma_t, normal vector); two windows (short l_s, long l_l), final score = max of the two Z-scores
- Detection: Z exceeding a threshold vs recent history flags the snapshot as a change point

**Main findings**
- On synthetic hybrid benchmarks (SBM with event and change injections) LAD beats activity-vector and TENSORSPLAT baselines at Hits@n on planted changes
- On UCI Message and Canadian Senate co-voting, detected change points align with known real-world events (term boundaries, government changes)
- Spectrum choice matters: Laplacian singular values outperform adjacency spectrum and raw activity statistics - connectivity structure, not volume, carries the signal

**Key takeaways**
- The direct published template for the KGF forensic protocol: per-document graph snapshot → Laplacian spectrum → dual-window Z-score → change points; then align with the probe trajectory
- Two-window design maps exactly to KGF needs: short window catches a single pathological document, long window catches slow drift (Heaps-class degradation)
- KGF's R09-H77 already found Fiedler-value sensitivity where JSD is blind but called it low-power at one eigenvalue; LAD says use the whole top-k spectrum, not one eigenvalue - the power upgrade path
- Cost at 10k nodes: truncated SVD on a sparse Laplacian is sub-second per snapshot; 200 snapshots trivially offline

**Tags**: #ChangePointDetection #DynamicGraphs #LaplacianSpectrum #SlidingWindow #StructuralAlarms

**Source**: https://arxiv.org/abs/2007.01229. Local: [paper] LAD Laplacian Change Point Detection, 2020-07.pdf
