**A Dynamical Theory of Sequential Retrieval in Input-Driven Hopfield Networks, Betteti, Baggio, Zampieri (AI4I Turin / Padova), 2026 (arXiv 2603.03201)**

The theory of what happens when you iterate. Static retrieval in associative memory is well understood; **sequential retrieval and multi-memory integration were previously supported only by numerical evidence**. This paper analyses an input-driven-plasticity Hopfield network as a two-timescale system - fast associative retrieval coupled to slow reasoning dynamics - and derives explicit conditions for self-sustained memory transitions.

**Key mechanism**
- Fast timescale: standard associative retrieval toward a fixed point. Slow timescale: input-driven plasticity reshapes the energy so the state can leave one memory and enter another
- The derived quantities are **gain thresholds** (how strong the drive must be for a transition to occur), **escape times** (how long the state dwells in one memory), and **collapse regimes** (where the sequence degenerates)

**Main findings**
- Self-sustained transition between stored memories requires the drive to exceed a gain threshold; below it the state stays put and iteration adds nothing
- Above a second threshold the dynamics enter a **collapse regime** - the trajectory no longer visits distinct memories
- The useful band between the two thresholds is narrow and parameter-dependent

**Key takeaways**
- Iterating retrieval is only productive inside a bounded gain window; outside it, iteration either changes nothing or collapses onto a degenerate state. There is no regime where "more iterations" is monotonically better
- The paper's own framing - that sequential retrieval theory was previously absent - means any multi-step Hopfield walk in a retrieval system is operating without published guarantees unless it instantiates this model
- Escape time gives the honest reading of "how many steps": it is set by the energy landscape, not chosen freely

**Tags**: #IteratedRetrieval #SequentialRetrieval #GainThreshold #Collapse #R59

**Source**: https://arxiv.org/abs/2603.03201. Local: [paper] Dynamical Theory Sequential Retrieval Hopfield, 2026.pdf
