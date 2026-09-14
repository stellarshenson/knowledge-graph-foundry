**Prototype Analysis in Hopfield Networks with Hebbian Learning, McAlister, Robins, Szymanski (University of Otago), Neural Computation 2024 (arXiv 2407.03342)**

The theory of when correlated examples collapse into a usable canonical memory - the closest published analogue of "snap entity mentions onto a prototype". Hebbian learning on highly correlated states normally degrades memory, but the same correlation can produce **prototype formation**: an **unlearned** stable state that represents a large correlated subset of the learned states, relieving the capacity problem.

**Key mechanism**
- Store many noisy examples of an underlying prototype (Bernoulli bit-flip noise parameter p) plus non-example states; the Hebbian weight matrix stabilises the prototype itself even though it was never presented
- The authors derive a **stability condition for the prototype state** as a function of (i) the number of examples presented, (ii) the noise in those examples, and (iii) the number of non-example states, and convert it into a probability of stability
- Extends to multiple concurrent prototypes; attractor strength grows with example count and with agreement among examples

**Main findings**
- Prototype formation succeeds when examples are numerous and mutually consistent (**crosstalk minimal**), and when representative vectors are far apart
- For **larger noise (Bernoulli p ≥ 0.3) prototype formation is disrupted**: the distance to the nearest prototype stays significant, and the selected attractors are very weak - the network has spurious states, not prototypes
- Below the example threshold, increasing the number of examples does not help; the failure is qualitative, not a matter of more data

**Key takeaways**
- A prototype-based merge only works in the low-noise, many-examples, well-separated-prototypes regime; outside it the attractors reached are **spurious states masquerading as prototypes**
- The stability condition is the published certificate for prototype-based identity, and it depends on the surface-form variance of the mentions - exactly the quantity an extraction-variance-dominated corpus makes large
- Prototypes emerge unlearned from the outer-product sum, which is the same construction as a Hebbian co-occurrence overlay

**Tags**: #PrototypeFormation #HebbianLearning #EntityCanonicalisation #StabilityCondition #R59

**Source**: https://arxiv.org/abs/2407.03342. Local: [paper] Prototype Analysis Hopfield Hebbian Learning, 2024.pdf
