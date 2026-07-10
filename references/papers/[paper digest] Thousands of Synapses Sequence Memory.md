# [paper digest] Why Neurons Have Thousands of Synapses, A Theory of Sequence Memory in Neocortex

**Why Neurons Have Thousands of Synapses, A Theory of Sequence Memory in Neocortex** (Hawkins & Ahmad, *Frontiers in Neural Circuits*, 2016; arXiv 1511.00083). A single HTM neuron with **several thousand** synapses on active dendrites learns to recognize **hundreds** of distinct patterns; sequence capacity scales **linearly** with synapse count; representations are sparse binary vectors (typically **~2%** active bits), giving super-exponential noise robustness as dimensionality grows. This is the peer-reviewed mechanistic core of Hawkins' claim that the fundamental cortical operation is learning and recalling sequences by continuous prediction.

## Key mechanism
- **Neuron as coincidence-detector array** - dendrites split into proximal (feedforward, drives the cell), basal (contextual, recognizes prior sequence state), and apical (feedback) zones; each dendritic segment fires when active synapses on it exceed a threshold, acting as an independent pattern detector
- **Prediction via depolarization** - basal-dendrite matches put the cell in a predictive (depolarized-but-not-spiking) state; a predicted cell that then receives feedforward input fires slightly earlier and inhibits neighbors in its mini-column, so prediction = the winning representation
- **Sequence memory** - the same feedforward input is represented by different active cells depending on context ("high-order" sequences); mini-columns give the union of possible next states, individual cells give the context-specific prediction
- **Learning rule** - Hebbian-style structural learning on binary synapses: grow synapses to the set of cells active on the previous step, punish segments that predicted wrongly; no backprop, online and unsupervised

## Main findings
- Capacity scales linearly with synapses/neuron - hence thousands of synapses are needed for real temporal streams
- Robust to large amounts of noise and to variation in the input patterns, because sparse high-dim SDR matches tolerate many missing/extra bits
- Continuous online learning: no separate train/test phase, adapts to changing statistics

## Key takeaways
- The engineering-usable primitives are: sparse high-dimensional binary signatures, context-dependent representation of the same token, and prediction-as-recognition (a correctly predicted input is recognized faster/preferentially)
- Content-addressable, distributed recall - a partial or noisy cue retrieves the stored next-state via SDR overlap, not by address lookup
- Companion SDR math (Ahmad & Hawkins 2015, arXiv 1503.07469) quantifies false-match probability and union capacity of sparse vectors

## Tags
`htm` `sequence-memory` `sparse-distributed-representation` `predictive-coding` `content-addressable-memory` `numenta` `hawkins`

## Source
- https://arxiv.org/abs/1511.00083 (PDF: https://arxiv.org/pdf/1511.00083)
- Journal: https://pmc.ncbi.nlm.nih.gov/articles/PMC4811948/
