**Modern Hopfield Networks and Attention for Immune Repertoire Classification, Widrich, Schäfl, Pavlović, Ramsauer, Gruber, Holzleitner, Brandstetter, Sandve, Greiff, Hochreiter, Klambauer (JKU Linz / Oslo), NeurIPS 2020 (arXiv 2007.13505)**

The flagship application of a Hopfield layer to massive multiple-instance learning - and, read carefully, a thin margin. DeepRC uses a modern Hopfield network with a **fixed query** as an attention pooling layer over hundreds of thousands of instances per bag.

**Key mechanism**
- Each immune repertoire is a bag of up to ~10^5 sequences; the Hopfield layer with a learned fixed query attends over all instances to pool them into a bag representation
- Exploits the exponential storage capacity to keep all instances addressable rather than sub-sampling

**Main findings**
- Real-world data: DeepRC average AUC **0.846 ± 0.223**, runner-up SVM with MinMax kernel **0.827 ± 0.210** - a 0.019 margin against a standard deviation of 0.22
- Real-world data with implanted motifs: DeepRC **0.980 ± 0.029**, second-best the burden test
- Wins on average AUC in all four data categories

**Key takeaways**
- The headline "outperforms all other methods" rests on a **0.019 AUC margin over a plain SVM** on the real-world category, well inside the reported spread; the decisive wins are on datasets with implanted synthetic signal
- The mechanism that carries the result is attention-pooling at extreme instance counts, which is a capacity story, not a retrieval-quality story
- Useful as calibration on how large a Hopfield-layer gain has actually been demonstrated on real data

**Tags**: #DeepRC #HopfieldLayer #MultipleInstanceLearning #ThinMargin #R59

**Source**: https://arxiv.org/abs/2007.13505. Local: [paper] Modern Hopfield Networks Immune Repertoire, 2020.pdf
