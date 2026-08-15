# How should the AI scientist organise its own thinking?

This folder holds the research behind one design decision: **what shape should the
multi-agent research process take?**

The question is not "which framework" but something closer to organisational design.
We have agents that can search literature, write into a knowledge graph, criticise
claims, and explain them. Almost any topology is buildable. The one we choose
determines what the system is capable of noticing — and, more importantly, what it is
capable of *missing without anyone realising*.

## Why research this rather than just pick something

The obvious move is an orchestrator that fans out searchers, collects results, and
summarises. That works, and it has a specific blind spot: every subagent sees the same
brief, returns to the same reader, and nothing in the structure is responsible for
disagreeing. The failure is silent. You get a confident synthesis whose confidence
comes from agents having been asked the same question rather than from the evidence
converging.

Human research organisations have hit this problem for a century and have developed
structural answers to it — appointed skeptics, independent estimation before
discussion, adversarial collaboration, the separation of generation from evaluation.
Individual thinkers have developed others: recording contrary evidence immediately,
atomic notes that can be recombined, explaining to a novice as a test of
understanding. Those are the mechanisms worth copying, because they were selected for
by the same pressure we are under.

So the method here is: study what demonstrably worked, enumerate the option space
exhaustively, then choose — and write down why, in the same form the pipeline itself
demands of a decision.

## The four investigations

| Document | Question |
|---|---|
| [`01-research-organisations.md`](01-research-organisations.md) | How did the most productive labs in history structure themselves, and what preceded their declines? |
| [`02-individual-methods.md`](02-individual-methods.md) | How did individual thinkers organise information so that it produced insight rather than merely accumulating? |
| [`03-inquiry-methodologies.md`](03-inquiry-methodologies.md) | What formal methods exist for structuring criticism, hypothesis elimination, and evidence synthesis, and which of them actually work? |
| [`04-agent-architectures.md`](04-agent-architectures.md) | What is the full option space of multi-agent topologies, and what does the evidence say about when more agents help? |

## The synthesis

| Document | Contents |
|---|---|
| [`05-topology-options.md`](05-topology-options.md) | The exhaustive enumeration: every orchestration option considered, with its coordination mechanism, cost profile, error-propagation behaviour, provenance quality, and failure mode. Including the ones we rejected, and why. |
| [`06-chosen-design.md`](06-chosen-design.md) | The design we adopted, traced to the evidence behind each choice, with the alternatives it beat and the conditions that should make us revisit it. |

## How to read this

If you want the answer, read `06-chosen-design.md`. If you want to challenge the
answer, read `05-topology-options.md` — it is written so that disagreeing with the
conclusion means pointing at a specific row.

The four investigation documents are the raw evidence. They are long and they are
meant to be skimmed by heading, not read through.

## A note on honesty in this folder

Multi-agent LLM research has a wide gap between claims and replicated results, and the
literature on creativity methodology has a wide gap between popularity and evidence.
Both are marked throughout. Where a celebrated method is probably folklore, these
documents say so; where a finding rests on a single vendor-authored paper, they say
that too. A design justified by weak evidence that presents itself as strong is worse
than an unjustified design, because nobody will revisit it.

Status: investigations in progress. This index was written first so the question is
fixed before the answers arrive — the same reason a `ProblemSpec` is written before a
stage runs.
