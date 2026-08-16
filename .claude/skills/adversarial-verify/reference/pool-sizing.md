# How verifier soundness caps the candidate pool

The instinct is: generate many candidates, let the filter sort it out. **The measured answer is
that the filter will not sort it out**, and the optimal pool is far smaller than the instinct
suggests — often single digits.

Three separate results converge on this, and they fail in different ways, which is why the
conclusion is robust.

---

## 1. Coverage keeps climbing; selection saturates

Repeated sampling scales coverage — the fraction of problems where *at least one* sample is
correct — enormously:

| Setting | 1 sample | Many samples |
|---|---|---|
| SWE-bench Lite, DeepSeek-Coder-V2 + Moatless | 15.9% | **56% @ 250** |
| MATH coverage, Llama-3-8B-Instruct | — | 79.8% @ 100 → **95.3% @ 10,000** |
| CodeContests, Gemma-2B | 0.02% | **7.1%** (>300×) |

And then the ceiling, in the same paper's words: *"all sample selection methods fail to reach
the coverage upper bound and saturate before reaching 100 samples"* — while coverage exceeds
95%. Mechanism: *"For some GSM8K and MATH problems, correct solutions are sampled with a
probability of 1% or lower, making them a minority of samples."*

**Coverage growth past roughly 100 samples is definitionally unrecoverable by voting.** A
correct answer present once in 250 draws is invisible to a majority vote and usually invisible
to a reward model too.

There is a theorem behind it: the accuracy of standard and weighted majority voting
**converges to a fixed limit** with infinite samples, determined only by the model's output
distribution. Not asymptotically approaching correctness — approaching a constant that may be
wrong.

## 2. The false-positive rate *rises* with N

This is the counter-intuitive one and it is the reason a pool cannot be scaled safely even
when a filter exists.

Sampling is memoryless, so per-draw false-positive probability is constant. Yet measured
false-positive rate climbs with N, because **task difficulty is strongly bimodal**: easy items
resolve in the first few draws and leave the pool, so the surviving population at high N is
dominated by hard items — exactly where the verifier is likeliest to admit something wrong.

The calibration number to internalise: real unit tests as a verifier came out at
**completeness 1.0, soundness 0.75** — perfect at admitting correct solutions, and admitting
**25% of incorrect ones**.

The formal bound: if `P_strong(correct) > P_weak(correct | passes verifier)`, then **no amount
of resampling the weak model matches one call to the strong model.** Resampling cannot decrease
the probability of a false positive, so it imposes *"an upper bound to the accuracy of
resampling-based inference scaling, regardless of compute budget."*

## 3. The optimum is small, and often zero

From the same work:

> *"even at zero computational cost, there is a finite optimal number of samples K that is
> often very low"*

- At a false-positive cost ratio of **4**: **K ≤ 5 for all four models tested.**
- At a relative false-positive cost of **10×**: **K = 0 for almost all models**, which the
  authors describe as *"effectively making them useless."*

And a separate result shows the shape is not merely flat but **non-monotonic**: vote-based
selection *"can first increase but then decrease as a function of the number of LM calls"*,
because more calls help on easy items and hurt on hard ones — so any task set mixing both has
an interior optimum.

Structured search shows the same pattern: beam search *"often underperform[s] the best-of-N
baseline"* as budget grows, and on easy questions *"degrades performance as the generation
budget increases"* — attributed to exploiting spurious verifier features. **A better search
over a worse verifier is worse.**

## Using `optimal_pool_size()`

```python
cal = VerifierCalibration(
    verifier="pose-scorer-v2",
    n_true_claims=80, n_true_admitted=76,      # completeness 0.95
    n_false_claims=40, n_false_admitted=8,     # soundness 0.80
)
cal.optimal_pool_size(false_positive_cost=4.0)   # -> 1
cal.optimal_pool_size(false_positive_cost=1.0)   # -> 5
```

It is an **order-of-magnitude guide, not a computed optimum** — the honest use is as a sanity
check against the instinct. If it returns 3 and the plan generates 500, the plan is relying on
a filter that has been measured and found insufficient.

Note what happens at `soundness = 1.0`: it returns `None`, meaning no ceiling is imposed by the
verifier and the pool should be scaled on budget instead. **Treat a measured soundness of
exactly 1.0 with suspicion** — it usually means too few falsehoods were injected to find the
failure mode, not that none exists.

## What to do instead of a bigger pool

In descending order of measured return:

1. **Improve verifier soundness.** It raises the ceiling on everything downstream, and it is
   the term with the largest exponent.
2. **Decorrelate the generators.** β, the all-wrong rate, is what bounds accuracy, and more
   samples from one model barely moves it — sampling spans **at most one effective dimension**
   within a single model at temperature 1, against about four across a multi-family ensemble.
3. **Sample from the checkpoint that maximises coverage, not pass@1.** For a pool, the
   RL-tuned checkpoint is often the wrong one: RLVR models beat their base models at k=1 but
   **underperform the base model at k=256–1024** across maths, code and visual reasoning
   — *"The observed reasoning abilities originate from and are bounded by the base model."*
   A repeated-sampling architecture and a pass@1-maximising checkpoint pull in opposite
   directions.
4. **Widen by input, not by output.** Rephrasing the *input* and aggregating beat
   self-consistency on **5 of 6 tasks at matched compute**, at roughly **1.8× accuracy per
   dollar**. Temperature is close to free in single-sample accuracy terms — changes from 0.0 to
   1.0 have no statistically significant effect — so widening the pool that way costs little,
   but it also buys little diversity compared to varying the input.
5. **Only then, more candidates.**

## The cost bar any pool-scaling proposal must clear

One elaborate tree-search scaffold reached 92.7% on HumanEval using **173,290 tokens and 28.42
node expansions** at k=10. In an independent cost-controlled evaluation, the same family of
method measured **$134.50 for 88.0%** against a plain temperature-warming retry baseline at
**93.2% for $2.45** — roughly **55× the cost for lower accuracy**. The general finding from
that evaluation: *"For substantially similar accuracy, the cost can differ by almost two orders
of magnitude."*

**Cost the baseline before proposing the scaffold.** Retry-with-warming is the baseline almost
nobody runs, and it wins more often than the literature admits.
