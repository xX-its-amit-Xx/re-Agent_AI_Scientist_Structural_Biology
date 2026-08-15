"""The interpretive and reasoning layers for the demo report.

Kept in its own module because it is the part worth *reading* as an example. Everything
here is written to the standard the contracts enforce:

* the layperson register uses no jargon that the glossary does not define,
* every implication names a stage, a decision, which way it argues, and what breaks
  if the interpretation is wrong,
* every reasoning step records the alternatives that were actually weighed and why
  each was rejected, plus the sources that informed the judgement.

Read `Audience.LAYPERSON` entries out loud. If one sounds like it is explaining
something to a colleague rather than to a stranger, it is not done.
"""

from __future__ import annotations

from reagent.contracts import (
    Audience,
    Confidence,
    Evidence,
    Glossary,
    GlossaryTerm,
    Implication,
    ImplicationStrength,
    Interpretation,
    Option,
    ReasoningStep,
    ReasoningTrace,
    SourceType,
    StepKind,
)


def paper(locator: str, title: str, year: int | None = None) -> Evidence:
    return Evidence(source_type=SourceType.PAPER, locator=locator, title=title, year=year)


def computation(path: str, title: str) -> Evidence:
    return Evidence(source_type=SourceType.COMPUTATION, locator=path, title=title)


# ---------------------------------------------------------------------------
# Glossary. Defined once for the run; the renderer makes each term hoverable
# wherever it appears in a plain-language passage.
# ---------------------------------------------------------------------------

GLOSSARY = Glossary(terms=[
    GlossaryTerm(
        term="nuclear receptor",
        aliases=["nuclear receptors"],
        plain=(
            "A family of proteins that sit inside a cell, catch a small molecule, and "
            "then switch genes on or off in response. They are how a cell notices "
            "something has arrived and changes its behaviour."
        ),
        why_it_matters=(
            "Our target is one of these, so its relatives are the natural first place "
            "to look for structures and measurements we can borrow."
        ),
        analogy=(
            "A thermostat: it senses one specific thing and, in response, turns a much "
            "larger system on or off."
        ),
    ),
    GlossaryTerm(
        term="ligand-binding domain",
        aliases=["LBD", "binding pocket", "pocket"],
        plain=(
            "The part of a protein shaped like a cavity, where a small molecule fits. "
            "Its size and shape decide which molecules can bind and which cannot."
        ),
        why_it_matters=(
            "Almost every prediction in this project is about what fits into this cavity, "
            "so its shape is the thing we most need to characterise."
        ),
        analogy="A lock: the shape of the keyhole determines which keys turn it.",
    ),
    GlossaryTerm(
        term="promiscuous",
        aliases=["promiscuity"],
        plain=(
            "Describes a protein that binds many chemically unrelated molecules rather "
            "than one specific partner. Usually it has a large, flexible cavity that can "
            "reshape itself around whatever arrives."
        ),
        why_it_matters=(
            "It makes prediction harder, because there is no single correct shape to aim "
            "for, and it means unrelated proteins with the same problem may be useful "
            "comparisons."
        ),
    ),
    GlossaryTerm(
        term="fold",
        aliases=["folds", "same fold", "shared fold"],
        plain=(
            "The overall three-dimensional shape a protein chain settles into. Two "
            "proteins can share a shape while having quite different chemical sequences."
        ),
        why_it_matters=(
            "Shape similarity is one of the ways we decide whether one protein's known "
            "structure can stand in for another's unknown one."
        ),
    ),
    GlossaryTerm(
        term="residue",
        aliases=["residues", "amino acid", "amino acids"],
        plain=(
            "One link in the chain that makes up a protein. There are twenty common "
            "kinds, and which ones line a cavity determines what sticks there."
        ),
        why_it_matters=(
            "When we say two cavities are similar, what we mean concretely is that the "
            "same kinds of links line them in the same places."
        ),
    ),
    GlossaryTerm(
        term="cytochrome P450",
        aliases=["CYP", "CYP3A4", "cytochrome"],
        plain=(
            "A family of enzymes, mostly in the liver, that chemically modify foreign "
            "substances so the body can clear them. They handle an enormous variety of "
            "molecules."
        ),
        why_it_matters=(
            "Our target switches these enzymes on, which is why a drug that activates it "
            "can change how quickly other drugs are cleared from the body."
        ),
    ),
    GlossaryTerm(
        term="template",
        aliases=["templates", "structural template"],
        plain=(
            "A known three-dimensional structure used as a starting shape when predicting "
            "an unknown one, on the assumption that related proteins look alike."
        ),
        why_it_matters=(
            "Which templates we choose is one of the biggest levers on prediction "
            "accuracy, and it is decided using the relationships found at this stage."
        ),
    ),
    GlossaryTerm(
        term="illustrative",
        plain=(
            "A label this project puts on any number that was written down as a "
            "placeholder rather than actually measured."
        ),
        why_it_matters=(
            "Every similarity score in this demonstration is a placeholder. The label is "
            "what stops a placeholder being read later as a result."
        ),
    ),
])


# ---------------------------------------------------------------------------
# Interpretations, keyed by finding id.
# ---------------------------------------------------------------------------

def interpretations() -> dict[str, Interpretation]:
    return {
        "F-CONSTRAINT-01": Interpretation(
            mechanism=(
                "Placeholder values enter a graph whenever the structure of an analysis "
                "is built before the measurements exist. They are harmless while labelled "
                "and dangerous once the label is lost, because nothing downstream can tell "
                "a placeholder from a measurement by looking at it."
            ),
            for_audience={
                Audience.LAYPERSON: (
                    "Every number in this demonstration was typed in by hand as a "
                    "stand-in, not measured. Each one is tagged as illustrative so it "
                    "cannot quietly turn into a result later. The shape of the analysis "
                    "is real; the numbers are not."
                ),
                Audience.ML_PRACTITIONER: (
                    "Treat this graph as schema validation only. Any model trained or "
                    "any template ranking derived from these edge weights would be "
                    "fitting to synthetic values."
                ),
            },
            implications=[
                Implication(
                    for_stage="all",
                    decision="whether any number from this graph may be used as input",
                    direction=(
                        "Argues AGAINST using any similarity score from this run, until "
                        "the corresponding tool has actually been run."
                    ),
                    strength=ImplicationStrength.DECISIVE,
                    if_wrong=(
                        "If a placeholder is treated as measured, every downstream ranking "
                        "inherits a fabricated ordering while looking fully cited."
                    ),
                ),
            ],
            caveat_for_reader=(
                "The relationships shown are real and drawn from the literature; only the "
                "numerical strengths attached to them are placeholders."
            ),
        ),

        "F-PROMISC-01": Interpretation(
            mechanism=(
                "A protein that must handle many unrelated molecules cannot achieve that "
                "with a tight, precisely shaped cavity. Selection therefore favours a "
                "large cavity with flexible walls. Because that is a shared engineering "
                "problem rather than a shared ancestry, proteins that solve it converge on "
                "similar cavity properties even when their chains are unrelated."
            ),
            for_audience={
                Audience.LAYPERSON: (
                    "Our target is unusual: it grabs many different molecules instead of "
                    "one. Other proteins in the body have the same job, notably the liver "
                    "enzymes that break down foreign substances. Those proteins are not "
                    "close relatives, but they had to solve the same problem, so their "
                    "cavities are roomy and adaptable in the same way. That makes them "
                    "useful comparisons even though a family tree would not group them "
                    "together."
                ),
                Audience.MEDICINAL_CHEMIST: (
                    "The promiscuity axis surfaces xenobiotic handlers rather than "
                    "receptor paralogs. For SAR that means selectivity liabilities are "
                    "more likely to sit outside the receptor family than inside it, and "
                    "an off-target panel chosen by homology will miss them."
                ),
                Audience.STRUCTURAL_BIOLOGIST: (
                    "Convergence on pocket plasticity without fold conservation. Pocket "
                    "similarity measures should therefore outrank sequence identity when "
                    "selecting comparison structures for this target."
                ),
                Audience.ML_PRACTITIONER: (
                    "A fine-tuning corpus assembled by family membership alone will be "
                    "missing the structures that share the actual difficulty. Weight by "
                    "measured pocket breadth as well as by taxonomy."
                ),
            },
            implications=[
                Implication(
                    for_stage="stage3_prior",
                    decision="which structures go into the template and fine-tuning corpus",
                    direction=(
                        "Argues FOR including promiscuous non-family proteins, weighted by "
                        "measured breadth of binding rather than by family membership."
                    ),
                    strength=ImplicationStrength.STRONG,
                    if_wrong=(
                        "The corpus is diluted with folds that share nothing useful, and "
                        "the fine-tune spends capacity on irrelevant structure."
                    ),
                ),
                Implication(
                    for_stage="stage2_biochem",
                    decision="which comparison structures to profile interactions against",
                    direction=(
                        "Argues FOR profiling at least one non-family promiscuous pocket, "
                        "to separate features general to adaptable pockets from features "
                        "specific to this receptor."
                    ),
                    strength=ImplicationStrength.SUGGESTIVE,
                    if_wrong=(
                        "Effort goes into a comparison that shares no mechanism, and the "
                        "resulting interaction map over-generalises from one family."
                    ),
                ),
            ],
            analogy=(
                "Cargo ships and moving vans are unrelated machines, but both must carry "
                "objects of unknown shape, so both end up as large adjustable boxes. If "
                "you want to learn how to hold awkward cargo, study either one."
            ),
            caveat_for_reader=(
                "Sharing the problem is not sharing the solution. These proteins are "
                "useful comparisons for pocket adaptability, not sources of transferable "
                "binding predictions."
            ),
        ),

        "F-NEG-01": Interpretation(
            mechanism=(
                "An unmeasured relationship and an absent relationship look identical in a "
                "graph unless the difference is recorded. Reporting only what was found "
                "therefore systematically overstates coverage, because the gaps are "
                "invisible."
            ),
            for_audience={
                Audience.LAYPERSON: (
                    "Most of the comparisons this stage was supposed to make have not been "
                    "made yet. That is worth saying plainly, because an unfinished check "
                    "looks exactly like a check that found nothing. Anyone reading further "
                    "should treat those areas as unknown rather than as settled."
                ),
                Audience.ML_PRACTITIONER: (
                    "Five of seven declared similarity axes are empty. Absence here is "
                    "missing data, not a measured zero, and any imputation that treats it "
                    "as zero will bias template selection toward the two populated axes."
                ),
            },
            implications=[
                Implication(
                    for_stage="stage2_biochem",
                    decision="whether to rely on this stage's neighbour ranking",
                    direction=(
                        "Argues AGAINST relying on it, and FOR running the missing axes "
                        "before any template ranking is trusted."
                    ),
                    strength=ImplicationStrength.DECISIVE,
                    if_wrong=(
                        "A ranking built on two of seven axes gets treated as complete, and "
                        "the neighbours that only the missing axes would surface never "
                        "appear at all."
                    ),
                ),
            ],
        ),

        "F-DESIGN-01": Interpretation(
            mechanism=(
                "Collapsing distinct relations into one generic link discards the very "
                "distinction a later query needs. Once two proteins are merely 'similar', "
                "there is no way to ask which kind of similarity held, so the graph can "
                "answer only vaguer questions than the data supports."
            ),
            for_audience={
                Audience.LAYPERSON: (
                    "Two proteins can be alike in several different ways: same shape, "
                    "same chemical sequence, same kind of cavity, or simply the same "
                    "family. We record each kind separately instead of saying only that "
                    "they are alike. That way a later question such as 'find me proteins "
                    "with a similar cavity that are not relatives' can actually be "
                    "answered."
                ),
                Audience.ML_PRACTITIONER: (
                    "One predicate per axis keeps the relations queryable and lets edge "
                    "weight stay normalised within its own scale, so a fold score and a "
                    "chemical similarity score are never silently compared."
                ),
            },
            implications=[
                Implication(
                    for_stage="all",
                    decision="how downstream stages query for comparison structures",
                    direction=(
                        "Argues FOR querying by named axis rather than by a generic "
                        "similarity threshold, so each query states which kind of "
                        "similarity it depends on."
                    ),
                    strength=ImplicationStrength.STRONG,
                    if_wrong=(
                        "Queries mix incommensurable scores, and a strong fold match and a "
                        "weak chemical match become indistinguishable."
                    ),
                ),
            ],
        ),
    }


# ---------------------------------------------------------------------------
# The reasoning trace: how the agent decided, and what it rejected.
# ---------------------------------------------------------------------------

def trace() -> ReasoningTrace:
    return ReasoningTrace(
        steps=[
            ReasoningStep(
                id="R-01",
                kind=StepKind.SCOPE,
                question="Should this stage measure similarity, or first establish the machinery that will hold the measurements?",
                options=[
                    Option(
                        name="measure first",
                        summary="Run Foldseek and RDKit immediately and record real numbers.",
                        rejected_because=(
                            "The graph schema, the axis definitions, and the report contract "
                            "were not settled, so measurements would have had to be "
                            "re-derived once they changed. Deferring costs one re-run; "
                            "getting the schema wrong costs every consumer."
                        ),
                        cost="a few hours of compute, repeated later",
                    ),
                    Option(
                        name="machinery first",
                        summary="Build the graph, axes, and report with labelled placeholders.",
                    ),
                ],
                chose="machinery first",
                because=(
                    "Three teammates are building stages against this stage's output "
                    "concurrently, so the interface is on the critical path and the numbers "
                    "are not. Placeholders that are labelled in the data itself let the "
                    "interface be exercised end to end without anyone mistaking the "
                    "contents for results."
                ),
                informed_by=[
                    computation("AGENTS.md", "the handoff contract three stages build against"),
                    paper("pmc:PMC9563780", "PXR ligand-binding pocket architecture", 2022),
                ],
                confidence_then=Confidence.SUPPORTED,
                revisit_if="the axis definitions stop changing, at which point measure immediately",
                produced_findings=["F-CONSTRAINT-01", "F-NEG-01"],
            ),
            ReasoningStep(
                id="R-02",
                kind=StepKind.METHOD_CHOICE,
                question="How should 'promiscuity' be operationalised as a measurable axis?",
                options=[
                    Option(
                        name="literature adjective",
                        summary="Treat a protein as promiscuous when papers describe it that way.",
                        rejected_because=(
                            "Not comparable across proteins and not reproducible: the label "
                            "reflects how much attention a protein has received as much as "
                            "how it behaves."
                        ),
                        cost="cheap but unusable",
                    ),
                    Option(
                        name="pocket volume",
                        summary="Rank by measured cavity volume.",
                        rejected_because=(
                            "Volume is necessary but not sufficient — a large rigid cavity "
                            "is selective — and it depends heavily on the pocket-detection "
                            "parameters, which makes cross-structure comparison fragile."
                        ),
                    ),
                    Option(
                        name="measured breadth of binding",
                        summary="Count distinct chemotypes a protein is recorded as binding.",
                    ),
                ],
                chose="measured breadth of binding",
                because=(
                    "Breadth of distinct chemotypes is the behaviour the axis is actually "
                    "about, is computable from public activity data, and degrades honestly: "
                    "a protein with little data ranks low and can be seen to be data-poor "
                    "rather than appearing selective."
                ),
                informed_by=[
                    paper("pmc:PMC8864553", "Promiscuity of the PXR ligand-binding domain", 2022),
                    computation(
                        ".claude/skills/target-neighborhood/SKILL.md",
                        "axis guidance: operationalise promiscuity as measured breadth, not an adjective",
                    ),
                ],
                confidence_then=Confidence.SUPPORTED,
                revisit_if=(
                    "a chemotype-clustering choice turns out to dominate the ranking, in "
                    "which case the clustering becomes the thing to justify"
                ),
                produced_findings=["F-PROMISC-01"],
            ),
            ReasoningStep(
                id="R-03",
                kind=StepKind.INCLUSION,
                question="Should non-family proteins be allowed onto the promiscuity axis at all?",
                options=[
                    Option(
                        name="family only",
                        summary="Restrict every axis to members of the target's own family.",
                        rejected_because=(
                            "It would exclude precisely the proteins that share the "
                            "structural problem, which is what the promiscuity axis exists "
                            "to surface. The family axis already covers relatives."
                        ),
                    ),
                    Option(
                        name="allow non-family",
                        summary="Admit any protein with comparable measured binding breadth.",
                    ),
                ],
                chose="allow non-family",
                because=(
                    "The axes are meant to be independent lenses. If every axis were "
                    "restricted to the family, they would return near-identical answers and "
                    "the point of having several would be lost. Convergent solutions to a "
                    "shared constraint are exactly the non-obvious transfer sources."
                ),
                informed_by=[
                    paper("pmc:PMC8864553", "Promiscuity of the PXR ligand-binding domain", 2022),
                    computation(
                        ".claude/skills/ai-scientist/reference/pxr-case-study.md",
                        "the reference pipeline deliberately harvested six non-receptor promiscuous classes",
                    ),
                ],
                confidence_then=Confidence.TENTATIVE,
                revisit_if=(
                    "a downstream template test shows non-family structures do not help, "
                    "which would make this a cost with no benefit"
                ),
                produced_findings=["F-PROMISC-01"],
            ),
            ReasoningStep(
                id="R-04",
                kind=StepKind.PARAMETER_CHOICE,
                question="How far from the target should the rendered graph view reach?",
                chose="two hops, with a per-node fan-out cap",
                because=(
                    "One hop shows only direct assertions and hides the shared-neighbour "
                    "structure that makes the graph worth drawing. Three hops on a hub node "
                    "produces an unreadable mat. Two hops with a cap keeps the strongest "
                    "edges and records what was dropped."
                ),
                no_alternative_because=(
                    "Not a real decision: one and three hops were both tried and rejected "
                    "on sight during development rather than evaluated, so recording them "
                    "as weighed options would overstate the rigour."
                ),
                informed_by=[
                    computation(
                        ".claude/skills/kg-visualize/reference/encoding-rules.md",
                        "truncation must be visible or the figure implies completeness",
                    ),
                ],
                confidence_then=Confidence.TENTATIVE,
                produced_artifacts=["docs/figures/demo_kg.html"],
            ),
            ReasoningStep(
                id="R-05",
                kind=StepKind.INTERPRETATION,
                question="Should each similarity axis get its own relation type, or one shared 'similar to' relation?",
                options=[
                    Option(
                        name="one generic relation",
                        summary="A single SIMILAR_TO edge with the axis recorded as an attribute.",
                        rejected_because=(
                            "Attributes are not indexed the way relation types are, so the "
                            "common query — one axis, excluding another — becomes a scan "
                            "with a filter, and the type system can no longer catch an edge "
                            "wired between the wrong kinds of entity."
                        ),
                    ),
                    Option(
                        name="one relation per axis",
                        summary="A distinct predicate per axis, each with its own score scale.",
                    ),
                ],
                chose="one relation per axis",
                because=(
                    "Downstream stages ask axis-specific questions, and each axis has its "
                    "own score scale that must not be compared with another's. Separate "
                    "predicates make both the query and the scale explicit, and let the "
                    "renderer normalise edge width within an axis instead of across all of "
                    "them."
                ),
                informed_by=[
                    computation("src/reagent/contracts/kg.py", "the controlled predicate vocabulary and its endpoint type table"),
                ],
                confidence_then=Confidence.SUPPORTED,
                produced_findings=["F-DESIGN-01"],
            ),
        ],
        open_decisions=[
            "Which chemotype clustering to use when computing binding breadth — deferred "
            "until there is real activity data to cluster.",
            "Whether the motif axis should use learned language-model features, published "
            "sequence motifs, or both. Deferred until the ESM-C credits are available.",
        ],
    )
