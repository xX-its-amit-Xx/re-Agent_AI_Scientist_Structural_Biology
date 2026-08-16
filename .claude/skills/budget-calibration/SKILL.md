---
name: budget-calibration
description: >-
  Size a compute run against a hard ceiling before spending any of it, using
  measured per-unit cost from a pilot rather than an estimate, and against the
  authoritative item count rather than a planning document. Produces an explicit
  allocation across generators, seeds, and reserve, plus the kill criteria that
  stop a run going bad. Use before any expensive dispatch or when deciding what
  fits. Trigger on: "how much will this cost", "size the run", "compute budget",
  "pilot run", "can we afford", "what fits in the budget", or /budget-calibration.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Budget calibration

The arithmetic is `items × generators × samples × cost-per-unit`, against a hard
ceiling. Every one of those four terms is routinely wrong on first estimate, and
they multiply, so the errors compound rather than cancel.

Get them measured before dispatching, because the failure mode is discovering at
70% spend that the plan never fit.

## The four terms

**Items.** Take this from the authoritative manifest, never from a planning
document, an announcement, or a README. These drift, and you are billed against the
real number. A documented instance: an announced count of 110 against a real count
of 184 — a 67% budget error, discovered only by counting the actual files.

Count the artifacts. Then count them again in the source the grader uses.

**Generators.** How many distinct models. Comes from `generator-diversity`'s pilot,
which should already have dropped the ones contributing no unique wins.

**Samples.** Seeds or samples per item per generator. This is the term that most
often turns out to be adjustable — the best@k curve says where it saturates, and
everything past saturation is refundable.

**Cost per unit.** **Measure this.** Run one real job end to end and record wall
time and money. Estimates here are wrong by multiples, because they omit cold
starts, retries, queueing, and the long tail of slow items.

## Measure, do not estimate

```python
def size_run(n_items, generators, samples, cost_per_unit, ceiling, reserve=0.20):
    """Return the plan and whether it fits under the ceiling with reserve held back."""
    jobs = n_items * len(generators) * samples
    projected = jobs * cost_per_unit
    usable = ceiling * (1 - reserve)
    return {
        "jobs": jobs,
        "projected": projected,
        "usable_ceiling": usable,
        "fits": projected <= usable,
        "headroom": usable - projected,
        "max_samples_that_fit": int(usable // (n_items * len(generators) * cost_per_unit)),
    }
```

`max_samples_that_fit` is the useful output. It converts "we cannot afford this"
into "here is the largest run we can afford", which is an actionable plan rather
than a blocked one.

## Hold a reserve

Commit **at most 70-80%** of the ceiling to the planned run.

The reserve pays for things that are not optional:

- **Reruns.** Some fraction of jobs fail and must be redone.
- **The rescue pass.** `tail-rescue` needs targeted generation late, on items you
  cannot identify until selection has run.
- **The rerun you did not plan.** A bug found after dispatch, a version bump, a
  metric correction.

A run that consumes 100% of the ceiling and then needs a small targeted rerun has
failed, and it has failed at the most expensive possible moment. The reserve is not
slack; it is the part of the plan that makes the rest usable.

## The pilot

Never size the full run from arithmetic alone.

1. Pick a small item subset — dozens, not hundreds.
2. Run every candidate generator at one sample.
3. Record **per generator**: median wall time, tail wall time, cost, failure rate,
   and unique-win count.
4. Extrapolate with the *tail*, not the median. The slow items dominate a large
   run's cost and they are exactly what a median hides.
5. Drop generators whose cost-per-unique-win is out of line. This is the number
   that matters — a cheap generator that never uniquely wins is worse value than an
   expensive one that regularly does.

The pilot is also where you discover that a generator fails on 15% of inputs, which
changes the plan far more than any cost estimate.

## Kill criteria

Write them before dispatch. A plan without kill criteria is a wish.

| Trigger | Action |
|---|---|
| Failure rate above the pilot's, by a clear margin | Halt; the inputs or the deployment differ from the pilot |
| Spend tracking above projection at the 25% mark | Halt and re-size; it will not self-correct |
| A generator's cost per unique win exceeds the threshold | Drop it mid-run and reallocate |
| Wall clock exceeds the deadline's implied rate | Cut samples, not items — partial coverage is usually worse than uniform thinning |

That last row is a real decision and it is worth pre-committing to. Reducing
samples degrades every item slightly; dropping items leaves holes, and on most
tasks a missing item scores worse than a mediocre one.

## Workflow

1. Read `problem.spec` for the ceiling, the deadline, and the authoritative item
   source. Count the items yourself from that source.
2. Run the pilot. Record the per-generator table.
3. Compute the plan with reserve held back. If it does not fit, report
   `max_samples_that_fit` rather than reporting failure.
4. Write kill criteria and the mid-run checkpoints that evaluate them.
5. Emit `method.budget_plan` and `method.cost_model`.
6. Track actual spend against projection at fixed checkpoints, not continuously and
   not only at the end.

## What the cost model is for

`method.cost_model` outlives this run. It is what makes the *next* estimate good,
and it is the only defence against re-measuring everything each time.

Record per generator: cost per unit, median and tail wall time, failure rate,
unique-win rate, and the date. Costs and performance both drift as deployments
change, so an undated cost model is a guess with a decimal point.

## Guard rails

- **Count items from the authoritative source.** Announcements and planning docs
  drift; billing does not.
- **Measure cost per unit; never estimate it.** Estimates are wrong by multiples in
  both directions.
- **Extrapolate from the tail, not the median.** Slow items dominate large runs.
- **Hold 20-30% in reserve.** Reruns and the rescue pass are not optional.
- **Write kill criteria before dispatch**, including which term you cut first.
- **Check spend at fixed checkpoints.** Overruns do not self-correct, and the 25%
  mark is where a correction is still cheap.
- **Never trust a deploy tool's exit status without checking its output.** Some
  print failures and exit zero, which turns a failed dispatch into a silent one.

## Anti-patterns

- **Sizing from a planning document.** The 110-versus-184 error, in general form.
- **Estimating per-unit cost from documentation** rather than from one real job.
- **Committing the full ceiling**, leaving nothing for the targeted rerun you will
  need.
- **Extrapolating from a median wall time**, then being surprised by the tail.
- **Dispatching the full run before the pilot**, on the grounds that the pilot is
  itself a cost. It is a small fraction of the run it protects.
- **Dropping items to stay under budget** without deciding in advance whether
  partial coverage or uniform thinning is worse for your metric.
- **Discovering the failure rate at scale**, when the pilot would have shown it.

## Handoff

`method.budget_plan` — the sized run, the allocation across generators and
samples, the reserve, the kill criteria, and the checkpoints — and
`method.cost_model`, the measured per-generator cost table with its date.

State the plan as a commitment with a stopping rule attached, not as a projection.
The projection is the least useful part; the stopping rule is what makes the number
safe to act on.
