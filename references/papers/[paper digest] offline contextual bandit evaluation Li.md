**An Unbiased Offline Evaluation of Contextual Bandit Algorithms with Generalized Linear Models (2012)**

The paper reviews and applies a data-driven offline evaluation technique for contextual bandit algorithms, replacing the standard practice of building a hand-crafted simulator (which unavoidably introduces modeling bias) with a rejection-sampling procedure over logged, randomly-served interaction data. The method provides **provably unbiased** estimates of an algorithm's total reward, with estimation error decreasing at rate **O(1/√L)** in the amount of logged data L, and is validated against real online bucket-test results from Yahoo! Front Page. As an application, the paper then uses this evaluator to compare bandit reward models built on generalized linear models (GLM) against the standard linear model, using **34M logged events** from a one-week random-traffic bucket.

**Key mechanism**
- Requires only that the logging policy chose each arm uniformly at random (or, with a weaker assumption, any randomized policy via rejection sampling); no simulator of the environment is built
- Policy Evaluator algorithm: step through the logged event stream one event `(x, a, r_a)` at a time; if the algorithm under test A, given its current history, would have chosen the same arm `a` as the logging policy did, keep the event (append to history, add reward to the running total); otherwise discard it entirely and move to the next event
- Because the logging policy picks uniformly among K arms, each event is retained independently with probability exactly 1/K - so the retained subsequence has exactly the same distribution as if drawn directly from the true environment D, which is what makes the reward estimate `Ĝ_A/T` unbiased
- Reward models compared under this evaluator: linear (`x·w_a`), logistic (`(1+exp(-x·w_a))^-1`), and probit (`Φ(x·w_a)`) generalized linear models, each with a Bayesian Gaussian posterior over the weight vector w_a, updated via Laplace approximation (logistic) or assumed-density-filtering/expectation-propagation (probit)
- Exploration policies layered on top of the reward posterior: ε-greedy (explore uniformly at random with probability ε) and UCB (`argmax_a E[r̂_a] + α·√Var[r̂_a]`, using closed-form mean/variance for linear/probit and one of four numerical approximations for logistic)
- Two-bucket evaluation design: a "learning" bucket runs the exploring algorithm and measures exploration/exploitation tradeoff quality directly; a "deployment" bucket runs the same model in pure-greedy mode to measure the quality of the learned point estimate in isolation

**Main findings**
- Logistic and probit GLMs substantially beat the linear model when rewards are binary (click/no-click), confirming the linear-model Gaussian-likelihood mismatch is a real cost, not just a theoretical concern
- Best linear-model-only baseline reaches nCTR of only **1.509 (learning) / 1.584 (deployment)**; GLM-based models clear this in every configuration tested
- UCB exploration consistently outperforms ε-greedy across all three reward models, despite lacking the regret guarantees that exist for linear-model UCB
- Optimistic initialization (setting the prior to over-estimate CTR, e.g. `N(0,I)` for logistic/probit) is alone sufficient to drive good exploration - turning off explicit ε/UCB exploration (`ε=α=0`) with an optimistic prior gives the *highest* learning-bucket nCTR observed, beating both ε-greedy and UCB with a non-optimistic prior
- Concretely: with a non-optimistic prior and no explicit exploration, mean nCTR was only 1.258 (σ=0.061); with an optimistic prior and no explicit exploration, it rose to 1.535 (σ=0.018) - a large, low-variance jump from prior choice alone
- Among four numerical approximations to the logistic posterior mean/UCB (M0-M3, U0-U3), three (U0, U2, U3) perform comparably well when their α is properly tuned; only U1 underperforms - the choice of closed-form approximation matters less than getting the exploration parameter right

**Key takeaways**
- An offline, rejection-sampling-based evaluator built from logged random-policy data is a practical way to A/B-compare scoring/selection policies without deploying them live or building a simulator - directly transferable to any setting with logged (context, action, outcome) triples from a randomized baseline
- Prior calibration (optimistic initialization) can substitute for explicit exploration heuristics and is cheaper to implement than ε-greedy or UCB - worth trying before adding an exploration mechanism
- Binary-outcome reward models should use a link function matched to the outcome distribution (logistic/probit) rather than defaulting to linear regression, even though linear models have the strongest existing regret theory
- Honest limitation: the offline evaluator requires the original logging policy to have been (effectively) randomized; it does not directly apply to evaluating against fully deterministic historical logs without falling back to propensity-scoring or doubly-robust estimation, which the paper only gestures at as an extension

**Relevance**
- The rejection-sampling offline evaluator is the natural fit for evaluating a small-model scorer or RL navigator's arm-selection policy against logged KGF ingestion/routing decisions without re-running the pipeline live - useful groundwork for the R51 "RL navigators" workstream if any navigator choice is framed as a contextual-bandit action
- The optimistic-initialization finding is a cheap, low-risk knob worth testing before adding heavier exploration machinery to any bandit-style component

**Tags**
- #ContextualBandits
- #OfflineEvaluation
- #GeneralizedLinearModels
- #ExplorationExploitation

**Source**
- Download: http://proceedings.mlr.press/v26/li12a/li12a.pdf
- Local: [paper] offline contextual bandit evaluation Li, 2012.pdf
