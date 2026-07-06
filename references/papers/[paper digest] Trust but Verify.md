# Trust but Verify! A Survey on Verification Design for Test-time Scaling

**Source**: https://arxiv.org/abs/2508.16665
**Authors**: Venktesh V (Stockholm University), Mandeep Rathee (L3S), Avishek Anand (TU Delft)
**Venue/Date**: Survey preprint (v3), September 2025

## Summary

This survey categorizes verification approaches for test-time scaling (TTS), where extra inference compute plus a verifier is used to search and select among candidate LLM outputs. It presents a unified view of verifier types, training mechanisms, and utility, and notes that verifier-based scaling increasingly outperforms verifier-free scaling as compute grows.

## Method

- Splits TTS into verifier-free (distill reasoning traces from a larger model) and verifier-based (external signal guides search over the solution space)
- Taxonomizes verifiers by target: outcome reward models (ORM) score final answers, process reward models (PRM) score each reasoning step, and hybrid ORM+PRM
- Taxonomizes by training: prompt-based, SFT discriminative, generative verifiers, and RL-based (GenRM, V-STaR, VerifierQ, PAV, RL-Tango, S2R)
- Surveys search/selection strategies: majority voting, pairwise ranking, best-of-N with reward models, and step-wise guided decoding
- Covers self-verification and multi-agent/multi-perspective verification

## Key Findings

- Scaling test-time compute without verifiers is suboptimal; the gap between verification-based and verifier-free scaling widens as compute increases (citing Setlur et al. 2025)
- Process-level verifiers (PRM) give finer-grained guidance than outcome-only verifiers but need step-level annotations
- Generative verifiers reformulate verification as generation to exploit LLM reasoning
- No prior work had unified categorization of verifier training and utility - this survey's contribution

## Relevance to KGF

- SUPPORTS H31 (small model in a verify-repair loop): the survey's central evidence is that adding a verifier to guide/select outputs beats unverified single-pass generation, and the gap grows with compute - the argument for a verify-repair loop over big-model single-pass
- Provides the design menu for KGF's self-auditing loop: outcome vs process verifiers, generative verifiers, and how to train them for extraction fidelity checking
- Reinforces that a verifier is a distinct component from the generator, aligning with a graph-as-quality-controller architecture that scores and repairs extracted content
