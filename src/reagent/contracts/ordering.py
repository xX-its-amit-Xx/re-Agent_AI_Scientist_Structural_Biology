"""Field order as a correctness property, not a style preference.

A schema handed to a model does not merely validate its output — under constrained
decoding it **fixes the order in which the model generates tokens**. So a schema that puts
a conclusion field before the field that derives it forces the model to commit to an answer
before doing the reasoning, and the reasoning that follows is then a rationalisation of a
commitment already made.

This is measured, and the effect is not small. Tam, Wu, Tsai, Lin, Lee & Chen ("Let Me
Speak Freely? A Study on the Impact of Format Restrictions on Performance of Large Language
Models", EMNLP 2024 Industry Track) report GSM8K accuracy falling from 86.51% to 23.44% for
one model when moving from free text to JSON with a schema. Their trace analysis locates the
cause precisely: **100% of the responses placed the ``answer`` key before the ``reason``
key**, which turns chain-of-thought prompting into direct answering. A follow-up from .txt
(Kurt, "Say What You Mean") reproduces the tasks with matched prompts and finds constrained
decoding to be roughly free — which isolates field order, rather than structure itself, as
the thing that costs accuracy.

That matters here more than in most projects, because nearly every inter-agent handoff in
this pipeline is a schema-forced object.

The distinction this module insists on
-------------------------------------
A naive rule — "all reasoning fields first" — would be wrong, and getting it wrong in the
other direction is also a cost. The rule applies to a field that **derives** the
conclusion, not to one that merely **supports** it.

* ``ReasoningStep.because`` derives ``chose``. Generating the choice first makes the
  justification post-hoc by construction. **Enforced.**
* ``Finding.evidence`` supports ``Finding.statement`` but does not derive it — the claim
  comes from reading sources, and the evidence list is the record of which ones. Forcing
  evidence first would ask an agent to assemble citations for a claim it has not yet
  stated, which is a different failure and not obviously a better one. **Not enforced.**

Getting that line wrong in either direction has a cost, so the enforced pairs are listed
explicitly rather than inferred from field names. ``candidate_violations`` exists to catch
*new* models by name heuristic, so that a schema added later gets looked at rather than
silently escaping the registry.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

#: Pairs that must appear in this order in a model's field list, with why.
#:
#: Keyed by model, then ``(derivation_field, conclusion_field)``. Verified by the test
#: suite, so reordering a model's fields fails CI rather than quietly degrading the
#: generation order of every agent that fills it.
ENFORCED_ORDER: dict[str, list[tuple[str, str, str]]] = {
    "ReasoningStep": [
        (
            "because", "chose",
            "The justification must be generated before the choice. Emitting `chose` first "
            "makes `because` a rationalisation of a commitment already made, which is "
            "exactly the trace pattern that collapsed GSM8K accuracy in Tam et al. It also "
            "defeats the point of the trace: a reader cannot tell a reason from an excuse, "
            "and neither can the model that wrote it.",
        ),
    ],
    "MetaProperty": [
        (
            "why_it_connects", "implies_predicates",
            "The mechanism must be stated before the predicates it licenses. Reversed, the "
            "agent picks predicates that look plausible for the property name and then "
            "writes a mechanism to fit — which is how `family_membership` ends up licensing "
            "a fold search because both sound structural.",
        ),
    ],
    "Implication": [
        (
            "direction", "strength",
            "Which side the finding argues for must precede how strongly. A strength "
            "generated first anchors the direction to whatever justifies that magnitude.",
        ),
    ],
    "Verdict": [
        (
            "because", "refuted",
            "The specific failure must be worked out before the verdict is named. A verdict "
            "generated first is a coin flip with a justification attached, and a verifier "
            "that has already said 'refuted' will find a reason. This is the same pattern "
            "Tam et al. traced to the GSM8K collapse, applied to the component with the "
            "largest measured return in the pipeline.",
        ),
    ],
}


#: Field ordering is the cheap half of the fix. The expensive half is not to force a schema
#: over the reasoning at all.
#:
#: Constrained decoding itself is roughly free — a matched-prompt reproduction found
#: structured output at or above unstructured across every task. What costs accuracy is
#: making a model reason *inside* a schema, and the measured drop is large: GSM8K accuracy
#: fell from 86.51% to 23.44% for one model under JSON-with-schema, and *"stricter format
#: constraints generally lead to greater performance degradation in reasoning tasks"*
#: (Tam, Wu, Tsai, Lin, Lee & Chen, EMNLP 2024 Industry Track).
#:
#: So for any stage where the *judgement* is hard rather than the formatting:
#:
#:   1. **Reason unconstrained.** Free-form, no schema, no field names.
#:   2. **Serialise separately.** A second call whose only job is to fill the schema from
#:      the reasoning it was handed.
#:
#: That buys the grounding gain of schema forcing without paying for it in reasoning
#: quality, and it is strictly better than field ordering alone because ordering only helps
#: when the reasoning happens to fit the schema's shape.
#:
#: Where the judgement is easy and the formatting is the whole task — extracting an
#: accession, normalising a score — single-pass schema forcing is correct and cheaper.
TWO_STAGE_GUIDANCE = (
    "Reason unconstrained, then serialise in a separate call. Field ordering helps only "
    "when the reasoning fits the schema's shape; splitting the calls always helps."
)

#: Field-name fragments that suggest a field carries reasoning.
_DERIVATION_HINTS = re.compile(
    r"^(?:because|why|reason|rationale|mechanism|derivation|justification|basis|"
    r"evidence_basis|argument|analysis|thinking|how_known)"
    r"|_(?:because|why|reason|rationale|basis)$",
    re.I,
)

#: Field-name fragments that suggest a field carries a conclusion.
_CONCLUSION_HINTS = re.compile(
    r"^(?:chose|choice|answer|verdict|conclusion|decision|result|score|rating|"
    r"confidence|strength|label|classification|selected|recommendation|saturated)$",
    re.I,
)


def check_order(model: type[BaseModel]) -> list[str]:
    """Registered ordering violations for one model. Empty means it is correct."""
    rules = ENFORCED_ORDER.get(model.__name__, [])
    if not rules:
        return []
    order = list(model.model_fields)
    problems: list[str] = []
    for derivation, conclusion, why in rules:
        if derivation not in order or conclusion not in order:
            problems.append(
                f"{model.__name__}: ordering rule names {derivation!r} before "
                f"{conclusion!r} but the model has no such field — the rule is stale and "
                "is silently enforcing nothing"
            )
            continue
        if order.index(derivation) > order.index(conclusion):
            problems.append(
                f"{model.__name__}: {conclusion!r} is generated before {derivation!r}. {why}"
            )
    return problems


def candidate_violations(model: type[BaseModel]) -> list[str]:
    """Name-heuristic scan, to surface models that should be *considered* for the registry.

    Advisory and deliberately noisy. Its job is to make a newly added schema get looked at,
    not to be right — a field named ``confidence`` after a field named ``mechanism`` may be
    fine, and the registry is where that judgement is recorded once made.
    """
    order = list(model.model_fields)
    first_conclusion = next(
        (i for i, f in enumerate(order) if _CONCLUSION_HINTS.match(f)), None
    )
    if first_conclusion is None:
        return []
    later_derivations = [
        f for f in order[first_conclusion + 1:] if _DERIVATION_HINTS.match(f)
    ]
    if not later_derivations:
        return []
    known = {d for d, _c, _w in ENFORCED_ORDER.get(model.__name__, [])}
    unreviewed = [f for f in later_derivations if f not in known]
    if not unreviewed:
        return []
    return [
        f"{model.__name__}: {unreviewed} look like derivation fields but are generated "
        f"after {order[first_conclusion]!r}. Decide whether each one *derives* that "
        "conclusion (reorder, and add to ENFORCED_ORDER) or merely *supports* it (leave, "
        "and say so in the field description)."
    ]


def audit(*models: type[BaseModel]) -> tuple[list[str], list[str]]:
    """``(violations, candidates)`` across several models, for CI and the CLI."""
    violations: list[str] = []
    candidates: list[str] = []
    for m in models:
        violations += check_order(m)
        candidates += candidate_violations(m)
    return violations, candidates
