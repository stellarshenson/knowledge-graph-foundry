**Daydreaming Hopfield Networks and their Surprising Effectiveness on Correlated Data, Serricchio, Bocchi, Chilin, Marino, Negri, Cammarota, Ricci-Tersenghi (Sapienza / Firenze / CNR), Neural Networks 2025 (arXiv 2405.08777)**

The published method for removing spurious blended states while keeping the real ones. Daydreaming perpetually reinforces the patterns to be stored (Hebb) and simultaneously **erases spurious memories** (dreaming/unlearning), converging asymptotically to stationary retrieval maps rather than destroying the memory as classic unlearning can.

**Key mechanism**
- Alternate Hebbian reinforcement of stored examples with an anti-Hebbian erasure step applied to states the network's own dynamics reach spontaneously - the spurious attractors
- Non-destructive: the procedure has a fixed point, unlike one-shot unlearning schemes

**Main findings**
- On random uncorrelated examples: optimal basin sizes and reconstruction quality
- On **correlated** data from a random-features model, Daydreaming **spontaneously exploits the correlations**, increasing storage capacity and basin size further, and stabilises the hidden features
- On MNIST it produces attractors close to unseen examples and to class prototypes

**Key takeaways**
- Correlated patterns - the regime real entity embeddings live in - are not automatically fatal; with an explicit spurious-state erasure step, correlation becomes usable structure
- The attractors it produces on real data are **class prototypes**, which is the object an identity-canonicalisation scheme wants
- The cost is an iterative training procedure over the pattern matrix, not a one-shot construction

**Tags**: #Daydreaming #Unlearning #SpuriousStates #CorrelatedData #Prototypes #R59

**Source**: https://arxiv.org/abs/2405.08777. Local: [paper] Daydreaming Hopfield Networks, 2024.pdf
