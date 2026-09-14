**STanHop: Sparse Tandem Hopfield Model for Memory-Enhanced Time Series Prediction, Wu, Hu, Li, Chen, Liu (Northwestern / NTU), ICLR 2024 (arXiv 2312.17346)**

An applied sparse-Hopfield architecture, and the source of the **Generalized Sparse Modern Hopfield Model**. STanHop blocks learn temporal and cross-series representations in two tandem sparse Hopfield layers, stacked hierarchically for multi-resolution features with resolution-specific sparsity.

**Key mechanism**
- Two sparse Hopfield layers in sequence: one over time, one across series, both storing data-dependent representations
- Two external memory modules: a **Plug-and-Play** module for train-less memory augmentation and a **Tune-and-Play** module for task-aware augmentation, so the network can respond to sudden events by consulting an external memory bank

**Main findings**
- The generalised sparse modern Hopfield model gives a **tighter memory-retrieval error bound than the dense counterpart without sacrificing memory capacity**
- Validated on synthetic and real-world multivariate time-series prediction

**Key takeaways**
- The plug-and-play external memory is the published pattern for "attach a retrievable pattern bank to a trained model without retraining" - the shape any bolt-on Hopfield store would take
- Reinforces the sparse-beats-dense error-bound result from a second direction and at architecture scale

**Tags**: #STanHop #SparseHopfield #ExternalMemory #TimeSeries #R59

**Source**: https://arxiv.org/abs/2312.17346. Local: [paper] STanHop Sparse Tandem Hopfield, 2023.pdf
