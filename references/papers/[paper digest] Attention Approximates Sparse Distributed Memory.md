**Attention Approximates Sparse Distributed Memory, Bricken, Pehlevan (Harvard), NeurIPS 2021 (arXiv 2111.05498)**

The second independent reduction of attention to an associative memory. Transformer attention closely approximates **Kanerva's Sparse Distributed Memory (SDM, 1988)** in the regime where SDM's Hamming-distance read operation is well approximated by an exponential weighting - and the correspondence pins β: attention's softmax temperature maps onto SDM's hard read radius.

**Key mechanism**
- SDM read: query a set of hard addresses within Hamming distance d, average the values stored there - a **threshold (top-k) separation** over a Hamming similarity
- The paper shows the exponential in attention's softmax approximates this threshold over a broad, biologically relevant parameter range, giving a closed correspondence between the softmax β and the SDM read radius
- SDM maps onto cerebellar circuitry, giving the analogy a neural substrate

**Main findings**
- Attention ≈ SDM read; the correspondence is tightest at particular β values, and trained transformers' learned β values sit near the SDM-optimal range
- SDM's threshold and attention's softmax are two separation functions producing near-identical retrieval over the operative range

**Key takeaways**
- Combined with Millidge's UHN framing, this closes the reduction question: **top-k retrieval and softmax attention are the same operation at different points on one separation axis**, not different mechanisms
- A system already doing dense top-k has already chosen a separation function; swapping to softmax(β) is a re-parameterisation, not a new capability

**Tags**: #SDM #Attention #Kanerva #Separation #Reduction #R59

**Source**: https://arxiv.org/abs/2111.05498. Local: [paper] Attention Approximates Sparse Distributed Memory, 2021.pdf
