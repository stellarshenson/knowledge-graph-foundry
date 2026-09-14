**Hopular: Modern Hopfield Networks for Tabular Data, Schäfl, Gruber, Bitto-Nemling, Hochreiter (JKU Linz), 2022 (arXiv 2206.00664)**

The clearest demonstration that a Hopfield layer's value is **storing the whole training set as retrievable patterns**, not sharpening a similarity. Hopular is a deep-learning architecture for small and medium tabular datasets in which every layer can access the original input **and the entire training set** via modern Hopfield retrieval.

**Key mechanism**
- The training set itself is the stored pattern matrix; each layer issues Hopfield retrievals against it, so the model behaves like an iterative refinement of the prediction using stored samples as explicit references
- Missing-feature imputation and reasoning about feature dependencies both fall out of pattern completion

**Main findings**
- Outperforms gradient-boosting and other deep-learning methods on small tabular datasets (fewer than 1,000 samples), the regime where deep learning usually loses
- On medium tabular datasets the advantage narrows to parity with strong gradient-boosting baselines

**Key takeaways**
- The mechanism that pays is **explicit access to stored instances**, which a retrieval system already has by construction - a Hopfield layer buys nothing extra when the pattern bank is already queryable
- The demonstrated regime is small-data, where memorising the training set is the win; it is not evidence about large pattern banks
- Together with CLOOB and DeepRC, this completes the picture of where Hopfield layers have genuinely paid: instance access at extreme counts or extreme scarcity, not retrieval quality

**Tags**: #Hopular #TabularData #InstanceRetrieval #SmallData #R59

**Source**: https://arxiv.org/abs/2206.00664. Local: [paper] Hopular Tabular Modern Hopfield, 2022.pdf
