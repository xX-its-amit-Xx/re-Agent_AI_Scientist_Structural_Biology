"""Tests for the interpretive and reasoning layers.

The guards here are the ones that make the difference between a report that *has* an
explanation field and a report that is actually explained. Two matter most:

* the plain-language check, because "write for a layperson" as an instruction reliably
  produces jargon in a friendlier tone, and
* the alternatives check on a reasoning step, because a default recorded as a decision
  turns an audit trail into post-hoc justification.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from reagent.contracts import (
    Audience,
    Confidence,
    Evidence,
    Finding,
    FindingKind,
    Glossary,
    GlossaryTerm,
    Implication,
    ImplicationStrength,
    Interpretation,
    ModelReport,
    Option,
    ReasoningStep,
    ReasoningTrace,
    SourceType,
    Stage,
    mean_sentence_length,
    undefined_jargon,
)

# --------------------------------------------------------------------------
# jargon detection — the mechanism behind the plain-language guarantee
# --------------------------------------------------------------------------


def test_jargon_detected_and_satisfied_by_the_glossary():
    text = "The ligand-binding domain is hydrophobic, and the fold is conserved."
    assert undefined_jargon(text, set()) == ["fold", "hydrophobic", "ligand-binding domain"]
    assert undefined_jargon(text, {"ligand-binding domain", "hydrophobic", "fold"}) == []


def test_defining_a_compound_term_covers_its_parts():
    """Defining 'ligand-binding domain' should not leave bare 'domain' flagged."""
    text = "The ligand-binding domain is roomy."
    assert undefined_jargon(text, {"ligand-binding domain"}) == []


def test_ordinary_english_is_not_flagged():
    """The check is useless if it fires on normal words; ambiguous terms need collocation."""
    for ok in (
        "The protein folds into a shape that lets it hold many different molecules.",
        "This series of experiments took a long time to seed and grow.",
        "The template for the report is in the docs folder.",
    ):
        assert undefined_jargon(ok, set()) == [], f"false positive on: {ok}"


def test_technical_collocations_are_flagged():
    assert "fold" in undefined_jargon("They share the same fold.", set())
    assert "domain" in undefined_jargon("The binding domain is large.", set())


def test_sentence_length_measure():
    # "Short" is one word, "Also short" is two, so the mean is 1.5.
    assert mean_sentence_length("Short. Also short.") == 1.5
    assert mean_sentence_length("One two three four five.") == 5.0
    assert mean_sentence_length("") == 0.0


# --------------------------------------------------------------------------
# Interpretation
# --------------------------------------------------------------------------


def _plain() -> str:
    return (
        "Two proteins can have different recipes and still end up with similar shaped "
        "pockets. That matters because the shape decides which small molecules fit."
    )


def an_implication(**kw) -> Implication:
    defaults = dict(
        for_stage="stage3_prior",
        decision="which structures to use as templates",
        direction="Argues FOR including non-family proteins with comparable pockets.",
        strength=ImplicationStrength.SUGGESTIVE,
        if_wrong="The template set is diluted and selection gets noisier.",
    )
    defaults.update(kw)
    return Implication(**defaults)


def test_layperson_register_is_required():
    with pytest.raises(ValidationError, match=r"must include Audience\.LAYPERSON"):
        Interpretation(for_audience={Audience.MEDICINAL_CHEMIST: "Some expert sentence here."})


def test_layperson_register_must_say_something():
    with pytest.raises(ValidationError, match="too short to explain anything"):
        Interpretation(for_audience={Audience.LAYPERSON: "It matters."})


def test_plain_language_check_catches_jargon_and_long_sentences():
    it = Interpretation(
        for_audience={
            Audience.LAYPERSON: (
                "The ligand-binding domain is promiscuous, which means it exhibits "
                "polypharmacology across many chemotypes."
            )
        }
    )
    problems = it.check_plain_language()
    assert problems, "jargon dressed in a friendly tone must still be caught"
    assert "undefined jargon" in problems[0]

    # Defining the terms on the interpretation itself satisfies the check.
    it2 = Interpretation(
        for_audience={Audience.LAYPERSON: it.for_audience[Audience.LAYPERSON]},
        glossary=[
            GlossaryTerm(term="ligand-binding domain",
                         plain="The cavity in a protein where a small molecule fits.",
                         why_it_matters="Its shape decides what can bind, which is the whole question."),
            GlossaryTerm(term="promiscuous",
                         plain="Binds many unrelated molecules rather than one specific partner.",
                         why_it_matters="It makes prediction harder because there is no single target shape."),
            GlossaryTerm(term="polypharmacology",
                         plain="One molecule acting on several different proteins.",
                         why_it_matters="It is where unexpected side effects usually come from."),
            GlossaryTerm(term="chemotype",
                         plain="A group of molecules that share a core chemical shape.",
                         why_it_matters="Grouping by chemotype is how we tell whether test molecules are new."),
        ],
    )
    assert it2.check_plain_language() == []


def test_a_run_glossary_satisfies_every_finding():
    """Define a term once for the report, not once per finding."""
    it = Interpretation(
        for_audience={
            Audience.LAYPERSON: (
                "The fold is shared between these two proteins, which is why one can "
                "stand in for the other when predicting a shape."
            )
        }
    )
    assert it.check_plain_language() != []
    assert it.check_plain_language(extra_defined={"fold"}) == []


def test_long_sentences_are_flagged():
    long_one = " ".join(["word"] * 60) + "."
    it = Interpretation(for_audience={Audience.LAYPERSON: long_one})
    assert any("words per sentence" in p for p in it.check_plain_language())


def test_implication_must_take_a_side():
    """The earlier version accepted a bare "for", so "relevant for X" passed untouched."""
    for vague in (
        "This is relevant to how templates get chosen later on.",
        "Relevant for template selection in the next stage.",
        "It concerns which templates end up being used here.",
    ):
        with pytest.raises(ValidationError, match="does not take a side"):
            an_implication(direction=vague)

    for pointed in (
        "Argues AGAINST using sequence identity as the ranker.",
        "Rules out sequence identity as the primary ranker.",
        "Favours the promiscuity axis over the family axis here.",
        "Raises the weight placed on measured binding breadth.",
    ):
        assert an_implication(direction=pointed)


def test_implication_stage_must_exist():
    """A typo'd stage addresses nobody, yet stages_affected() would report it as real."""
    with pytest.raises(ValidationError, match="is not a stage"):
        an_implication(for_stage="stage9_nonexistent")
    assert an_implication(for_stage="all"), "'all' stays expressible for general implications"
    assert an_implication(for_stage="stage2_biochem")


def test_glossary_definitions_are_checked_for_circularity():
    """Defining jargon with more jargon moves the problem rather than solving it."""
    circular = Glossary(terms=[
        GlossaryTerm(
            term="promiscuous",
            plain="A protein that exhibits polypharmacology across many chemotypes.",
            why_it_matters="It makes the prediction problem harder to pin down.",
        ),
    ])
    problems = circular.circular_definitions()
    assert "promiscuous" in problems
    assert set(problems["promiscuous"]) >= {"chemotype", "polypharmacology"}

    plain = Glossary(terms=[
        GlossaryTerm(
            term="promiscuous",
            plain="Describes a protein that binds many unrelated molecules rather than one.",
            why_it_matters="It makes prediction harder because there is no single target shape.",
        ),
    ])
    assert plain.circular_definitions() == {}


def test_report_surfaces_circular_glossary_definitions():
    r = _report(
        plain_summary=(
            "We looked for proteins that resemble our target so we can borrow their "
            "known shapes. The most useful ones were not its close relatives."
        ),
        glossary=Glossary(terms=[
            GlossaryTerm(term="promiscuous",
                         plain="A protein that exhibits polypharmacology widely.",
                         why_it_matters="It makes the prediction problem harder."),
        ]),
    )
    assert any("defined using jargon nothing explains" in p
               for p in r.plain_language_problems())


def test_implication_records_its_own_failure_mode():
    """`if_wrong` is what makes an implication reviewable rather than just confident."""
    with pytest.raises(ValidationError):
        Implication(
            for_stage="stage3_prior",
            decision="which structures to use as templates",
            direction="Argues FOR including non-family proteins.",
            if_wrong="",
        )


def test_interpretation_reports_its_coverage():
    it = Interpretation(
        for_audience={
            Audience.LAYPERSON: _plain(),
            Audience.ML_PRACTITIONER: "Weight the corpus by measured breadth, not taxonomy.",
        },
        implications=[an_implication(), an_implication(for_stage="stage2_biochem")],
    )
    assert it.audiences_covered() == ["layperson", "ml_practitioner"]
    assert it.stages_affected() == ["stage2_biochem", "stage3_prior"]


# --------------------------------------------------------------------------
# Findings that a downstream stage acts on must be interpreted
# --------------------------------------------------------------------------


def _interp() -> Interpretation:
    return Interpretation(
        for_audience={Audience.LAYPERSON: _plain()}, implications=[an_implication()]
    )


@pytest.mark.parametrize(
    "kind",
    [FindingKind.PRIOR, FindingKind.DESIGN_CHOICE, FindingKind.NEGATIVE,
     FindingKind.CONSTRAINT],
)
def test_decision_bearing_kinds_require_interpretation(kind):
    ev = [Evidence(source_type=SourceType.PAPER, locator="doi:10.1/x")]
    with pytest.raises(ValidationError, match="needs an `interpretation`"):
        Finding(id="F-1", kind=kind, statement="A claim long enough to pass length checks.",
                confidence=Confidence.SUPPORTED, evidence=ev)
    assert Finding(id="F-1", kind=kind,
                   statement="A claim long enough to pass length checks.",
                   confidence=Confidence.SUPPORTED, evidence=ev,
                   interpretation=_interp())


@pytest.mark.parametrize("kind", [FindingKind.OBSERVATION, FindingKind.HYPOTHESIS,
                                  FindingKind.BENCHMARK, FindingKind.RISK])
def test_other_kinds_may_omit_interpretation(kind):
    """Advisory, not fatal — an uninterpreted observation is unhelpful, not dangerous."""
    ev = [Evidence(source_type=SourceType.PAPER, locator="doi:10.1/x")]
    assert Finding(id="F-1", kind=kind,
                   statement="A claim long enough to pass length checks.",
                   confidence=Confidence.SUPPORTED, evidence=ev)


# --------------------------------------------------------------------------
# ReasoningStep — the audit trail
# --------------------------------------------------------------------------


def a_step(**kw) -> ReasoningStep:
    from reagent.contracts import StepKind

    defaults = dict(
        id="R-01",
        kind=StepKind.METHOD_CHOICE,
        question="Which similarity axis should run first, given limited time?",
        options=[
            Option(name="fold first", summary="Run structural comparison first."),
            Option(name="sequence first", summary="Run sequence search first.",
                   rejected_because="Cheaper but weakly predictive for this target class."),
        ],
        chose="fold first",
        because=(
            "Fold similarity is the axis the downstream template decision depends on most "
            "directly, so it is worth the extra cost to have it early."
        ),
    )
    defaults.update(kw)
    return ReasoningStep(**defaults)


def test_a_single_option_is_a_default_not_a_decision():
    with pytest.raises(ValidationError, match="Either record"):
        a_step(options=[Option(name="fold first")])
    # Declaring it a default is accepted, and is what keeps the trace honest.
    s = a_step(options=[Option(name="fold first")],
               no_alternative_because="Only one structural aligner was installed.")
    assert s.no_alternative_because


def test_the_chosen_option_must_be_among_the_options():
    with pytest.raises(ValidationError, match="not among"):
        a_step(chose="pocket first")


def test_rejected_options_must_say_why():
    with pytest.raises(ValidationError, match="no `rejected_because`"):
        a_step(options=[Option(name="fold first"), Option(name="sequence first")])


def test_rejected_property_excludes_the_choice():
    s = a_step()
    assert [o.name for o in s.rejected] == ["sequence first"]


def test_trace_surfaces_defaults_uncited_steps_and_reversals():
    from reagent.contracts import StepKind

    cited = a_step(id="R-01", informed_by=[
        Evidence(source_type=SourceType.PAPER, locator="doi:10.1/a", title="A paper")
    ], superseded_by="R-03")
    plain = a_step(id="R-02")
    default = a_step(id="R-03", kind=StepKind.PARAMETER_CHOICE,
                     options=[Option(name="two hops")],
                     chose="two hops",
                     no_alternative_because="One and three hops were rejected on sight, not evaluated.")
    tr = ReasoningTrace(steps=[cited, plain, default],
                        open_decisions=["Which clustering to use for breadth."])
    assert tr.defaults() == ["R-03"]
    assert tr.uncited_steps() == ["R-02", "R-03"]
    assert tr.reversals() == [("R-01", "R-03")]
    assert tr.all_sources() == ["doi:10.1/a"]
    summary = tr.summary()
    assert "3 recorded decisions" in summary and "deliberately still open" in summary


def test_trace_rejects_duplicate_ids_and_dangling_supersedes():
    with pytest.raises(ValidationError, match="duplicate reasoning step id"):
        ReasoningTrace(steps=[a_step(id="R-01"), a_step(id="R-01")])
    with pytest.raises(ValidationError, match="not in this trace"):
        ReasoningTrace(steps=[a_step(id="R-01", superseded_by="R-99")])


def test_trace_links_findings_and_spots_orphans():
    s = a_step(produced_findings=["F-1"])
    tr = ReasoningTrace(steps=[s])
    assert tr.for_finding("F-1") == [s]
    assert tr.for_finding("F-2") == []
    assert tr.orphan_findings(["F-1", "F-2"]) == ["F-2"]


# --------------------------------------------------------------------------
# Report-level integration
# --------------------------------------------------------------------------


def _report(**kw) -> ModelReport:
    defaults = dict(
        report_id="r1", run_id="r", stage=Stage.LITERATURE, title="T",
        objective="Characterise the target neighbourhood.",
        executive_summary="A summary long enough to satisfy the minimum length rule here.",
        findings=[
            Finding(id="F-1", kind=FindingKind.PRIOR,
                    statement="Promiscuous non-family proteins are candidate transfer sources.",
                    confidence=Confidence.TENTATIVE,
                    evidence=[Evidence(source_type=SourceType.PAPER, locator="doi:10.1/x")],
                    interpretation=_interp()),
        ],
        limitations=["Only one axis populated."],
    )
    defaults.update(kw)
    return ModelReport(**defaults)


def test_report_merges_glossaries_and_checks_plain_language():
    r = _report(
        plain_summary=(
            "We looked for proteins that resemble our target so we can borrow their known "
            "shapes. The most useful ones turned out not to be its close relatives."
        ),
        glossary=Glossary(terms=[
            GlossaryTerm(term="fold",
                         plain="The overall three-dimensional shape a protein settles into.",
                         why_it_matters="Shape similarity is how we pick stand-in structures."),
        ]),
    )
    assert r.effective_glossary().get("fold") is not None
    assert r.plain_language_problems() == []


def test_report_flags_jargon_in_the_plain_summary():
    r = _report(plain_summary=(
        "The apo structure shows the ligand-binding domain is hydrophobic, so a "
        "pharmacophore model would be premature at this point in the work."
    ))
    problems = r.plain_language_problems()
    assert any("plain_summary uses undefined jargon" in p for p in problems)


def test_report_maps_implications_to_stages_and_counts_audiences():
    r = _report()
    assert r.implications_by_stage() == {
        "stage3_prior": [("F-1", "which structures to use as templates")]
    }
    assert r.audience_coverage() == {"layperson": 1}
    assert r.uninterpreted_findings() == []
    assert r.findings_without_implications() == []


def test_report_spots_trivia_and_missing_interpretation():
    bare = Finding(id="F-2", kind=FindingKind.OBSERVATION,
                   statement="A neighbour scores highly on the fold axis.",
                   confidence=Confidence.SUPPORTED,
                   evidence=[Evidence(source_type=SourceType.PAPER, locator="doi:10.1/y")])
    trivia = Finding(id="F-3", kind=FindingKind.OBSERVATION,
                     statement="Another neighbour scores highly on the fold axis.",
                     confidence=Confidence.SUPPORTED,
                     evidence=[Evidence(source_type=SourceType.PAPER, locator="doi:10.1/z")],
                     interpretation=Interpretation(
                         for_audience={Audience.LAYPERSON: _plain()}))
    r = _report(findings=[bare, trivia])
    assert r.uninterpreted_findings() == ["F-2"]
    assert r.findings_without_implications() == ["F-3"]


def test_report_reports_reasoning_gaps():
    r = _report()
    gaps = r.reasoning_gaps()
    assert any("no reasoning steps recorded" in g for g in gaps)

    r2 = _report(reasoning=ReasoningTrace(steps=[a_step(produced_findings=["F-1"])]))
    assert r2.reasoning_gaps() == [] or all(
        "no reasoning steps" not in g for g in r2.reasoning_gaps()
    )
    assert r2.reasoning_sources() == []


def test_report_roundtrips_the_new_layers(tmp_path):
    r = _report(
        plain_summary=(
            "We looked for proteins that resemble our target so we can borrow their known "
            "shapes. The most useful ones turned out not to be its close relatives."
        ),
        reasoning=ReasoningTrace(steps=[a_step(produced_findings=["F-1"], informed_by=[
            Evidence(source_type=SourceType.PAPER, locator="doi:10.1/a")
        ])]),
    )
    path = r.write(tmp_path / "report.json")
    back = ModelReport.load(path)
    assert back.plain_summary == r.plain_summary
    assert back.reasoning.steps[0].chose == "fold first"
    assert back.findings[0].interpretation is not None
    assert back.findings[0].interpretation.implications[0].for_stage == "stage3_prior"
    assert back.reasoning_sources() == ["doi:10.1/a"]


# --------------------------------------------------------------------------
# knowledge-telling: a fluent explanation is weak evidence of understanding
# --------------------------------------------------------------------------


def test_knowledge_building_catches_restatement():
    """Roscoe & Chi: explainers default to delivering knowledge, not developing it."""
    telling = Interpretation(
        for_audience={Audience.LAYPERSON: _plain()},
        mechanism="These two proteins are similar in the shape of their binding sites.",
        implications=[Implication(
            for_stage="stage3_prior", decision="which templates to use",
            direction="Argues FOR including them among the templates.",
            if_wrong="The template choice is suboptimal in some way.",
        )],
    )
    problems = telling.knowledge_building_problems()
    assert any("no causal language" in p for p in problems), (
        "a mechanism that restates the finding must be caught"
    )
    assert any("observable consequence" in p for p in problems)
    assert any("caveat_for_reader" in p for p in problems)


def test_knowledge_building_accepts_a_real_explanation():
    building = Interpretation(
        mechanism=(
            "A protein that must handle many unrelated molecules cannot achieve that with "
            "a tight cavity, so selection favours a large one with flexible walls."
        ),
        for_audience={Audience.LAYPERSON: _plain()},
        implications=[Implication(
            for_stage="stage3_prior", decision="which structures enter the corpus",
            direction="Argues FOR including promiscuous non-family proteins.",
            if_wrong="The corpus is diluted with folds that share nothing useful.",
        )],
        caveat_for_reader="Sharing the problem is not sharing the solution.",
    )
    assert building.knowledge_building_problems() == []


def test_consequence_matching_survives_english_morphology():
    """An earlier word-list version matched 'dilutes' but not 'diluted'."""
    from reagent.contracts.interpret import COMMITTING

    for inflected in ("is diluted with folds", "dilutes the corpus", "diluting the set",
                      "over-generalises from one family", "generalised badly",
                      "inherits a fabricated ordering", "effort is wasted"):
        assert COMMITTING.search(inflected), f"missed a real consequence: {inflected}"

    for mere_relevance in ("This is relevant to the next stage.",
                           "It concerns the template set.",
                           "The choice is important here."):
        assert not COMMITTING.search(mere_relevance), f"false positive: {mere_relevance}"


def test_causal_detection_discriminates():
    from reagent.contracts.interpret import CAUSAL

    assert CAUSAL.search("Selection favours a large cavity because it must handle many.")
    assert CAUSAL.search("The data no longer carries it, so the query cannot discriminate.")
    assert not CAUSAL.search("These two proteins are similar in shape.")


def test_report_surfaces_knowledge_telling_per_finding():
    bare = Finding(
        id="F-T", kind=FindingKind.PRIOR,
        statement="Promiscuous non-family proteins are candidate transfer sources.",
        confidence=Confidence.TENTATIVE,
        evidence=[Evidence(source_type=SourceType.PAPER, locator="doi:10.1/x")],
        interpretation=Interpretation(
            for_audience={Audience.LAYPERSON: _plain()},
            mechanism="They are alike in the relevant way.",
            implications=[an_implication()],
        ),
    )
    r = _report(findings=[bare])
    telling = r.knowledge_telling_findings()
    assert "F-T" in telling
    assert any("no causal language" in p for p in telling["F-T"])
