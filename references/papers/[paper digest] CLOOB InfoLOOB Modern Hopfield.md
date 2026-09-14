**CLOOB: Modern Hopfield Networks with InfoLOOB Outperform CLIP, Fürst, Rumetshofer, Lehner, Tran, Tang, Ramsauer, Kreil, Kopp, Klambauer, Bitto-Nemling, Hochreiter (JKU Linz / IARAI), NeurIPS 2022 (arXiv 2110.11316)**

A Hopfield success whose ablation is a null. CLOOB adds two things to CLIP: modern Hopfield retrieval over the batch (to amplify covariance structure and counter the explaining-away problem) and the InfoLOOB objective in place of InfoNCE. Together they improve zero-shot transfer.

**Key mechanism**
- Modern Hopfield retrieval replaces each embedding by a retrieval from a stored set, amplifying shared covariance structure; measured as an increase in the **number of effective eigenvalues** of the embedding covariance matrices during learning
- InfoLOOB removes the positive pair from the denominator, avoiding InfoNCE saturation

**Main findings**
- InfoLOOB with Hopfield considerably improves performance in **5 of 8 datasets at epoch 31 and 7 of 8 at epoch 128** over all other models
- **Ablation: "Both InfoLOOB and InfoNCE with Hopfield decrease the performance compared to InfoNCE in most of the tasks."** The Hopfield component alone is a regression
- The paper's own framing: "CLOOB balances the **overfitting of InfoLOOB with the underfitting of modern Hopfield networks**"

**Key takeaways**
- The clearest published statement that a modern Hopfield retrieval layer, dropped into an otherwise working pipeline, **underfits and degrades it** unless paired with a compensating objective change
- The Hopfield contribution is characterised as covariance amplification - a smoothing effect - which is the same operation family as averaging retrieved neighbours into a representation
- Any proposal to insert a Hopfield retrieval step into an existing dense pipeline should expect this ablation's sign by default

**Tags**: #CLOOB #CLIP #HopfieldAblation #NullResult #Underfitting #R59

**Source**: https://arxiv.org/abs/2110.11316. Local: [paper] CLOOB InfoLOOB Modern Hopfield, 2021.pdf
