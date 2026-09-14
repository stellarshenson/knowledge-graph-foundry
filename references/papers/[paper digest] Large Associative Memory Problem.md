**Large Associative Memory Problem in Neurobiology and Machine Learning, Krotov, Hopfield (MIT-IBM / Princeton), ICLR 2021 (arXiv 2008.06996)**

The microscopic theory underneath the modern Hopfield family. Dense associative memories appear to need many-body synaptic junctions; this paper shows they are the effective description of a two-layer network with **hidden neurons and only two-body interactions**, restoring biological plausibility and unifying the model zoo.

**Key mechanism**
- A visible layer and a hidden layer with pairwise couplings; the hidden-layer activation function determines which known model emerges
- Integrating out the hidden neurons recovers the earlier models, including Ramsauer et al.'s continuous modern Hopfield network
- Both the microscopic dynamics and the reduced dynamics minimise a Lyapunov energy

**Main findings**
- Provides an alternative derivation of the "Hopfield Networks is All You Need" energy and update rule and clarifies the relations among the variants
- The Lagrangian formulation makes the separation function an explicit design choice (the hidden-layer activation), which is the framing Millidge's UHN then generalises

**Key takeaways**
- Confirms that the whole family differs only in the choice of activation on a hidden layer over stored patterns - the separation axis again
- The generalised energy formalism is what later work (Energy Transformer, Hopfield-Fenchel-Young) builds on

**Tags**: #Krotov #Hopfield #EnergyFunction #Lagrangian #R59

**Source**: https://arxiv.org/abs/2008.06996. Local: [paper] Large Associative Memory Problem, 2020.pdf
