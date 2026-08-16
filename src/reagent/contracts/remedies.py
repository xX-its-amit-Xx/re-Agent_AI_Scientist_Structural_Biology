"""The known failure modes of a co-folding pipeline, and what to try for each.

The registry behind ``Experiment.if_then``. Two design commitments, both of which are about
what the registry is *not*.

**It is a router, not a reimplementation.** Almost every rung hands off to a skill that already
exists — ``structure-ensemble`` widens a pool, ``physics-rescoring`` and ``learned-rescoring``
add challenger signals, ``bottleneck-triage`` decides whether the problem is generation or
selection at all, ``significance-discipline`` decides whether an improvement is real. A remedy
that duplicates one of those is worse than a pointer to it, because it will drift.

**It is a floor, not a ceiling.** A fixed if-this-then-that table covers the failures somebody
has already met, which is most of them and never all of them. So every ladder ends at
``RemedyTier.NOVEL`` — escalate to research — and ``unanticipated_signals()`` reports what the
table missed so the next run's table is better. A registry presented as complete would be the
same failure as a search presented as exhaustive.

**Ordering is by cost, and that is the single most useful thing here.** The expensive remedies
are the interesting ones; the cheap ones resolve most failures. Left to choose freely, an agent
reaches for a fine-tuned model when the real problem was a tautomer — so the free rung comes
first and ``Experiment`` rejects an out-of-order ladder.
"""

from __future__ import annotations

from reagent.contracts.experiment import FailureSignal, Remedy, RemedyTier


def _r(action: str, tier: RemedyTier, rationale: str, skill: str | None = None,
       effect: str | None = None) -> Remedy:
    return Remedy(action=action, tier=tier, rationale=rationale, via_skill=skill,
                  expected_effect=effect)


#: The three checks that come before any diagnosis, for every signal.
#:
#: A bad number can mean a bad model or a bad measurement, and the second costs nothing to rule
#: out. Skipping this is how an afternoon gets spent deepening an MSA for a complex whose ligand
#: SMILES had the wrong stereocentre.
UNIVERSAL_FIRST: list[Remedy] = [
    _r("Re-read the inputs as the pipeline actually received them: protonation state, tautomer, "
       "stereocentres, canonical SMILES round-trip, chain selection, and whether any "
       "crystallisation artefact was passed in as the ligand.",
       RemedyTier.FREE,
       "A mangled input produces exactly the signature of a model failure and is free to rule "
       "out. Chain selection has already cost this project once — picking by length selected a "
       "partner protein and gave 26% identity instead of 44%.",
       "binder-census",
       "If this was it, the corrected input fixes the metric outright rather than improving it."),
    _r("Verify the harness measures what is being graded: run the identity test, confirm the "
       "metric matches the official one, and check the reference structure and units.",
       RemedyTier.FREE,
       "An unverified scorer can report a failure that did not happen. Symmetric ligands, a "
       "wrong reference pose and a units mismatch all produce plausible bad numbers.",
       "harness-verification",
       "A passing identity test moves the doubt from the metric to the model."),
    _r("Check the difference against the noise floor before treating it as a failure at all.",
       RemedyTier.FREE,
       "A metric worse than a baseline by less than the bootstrap interval is not a failure, "
       "and chasing it tunes the pipeline to noise.",
       "significance-discipline",
       "An overlapping interval means there is nothing to fix."),
]


#: Failure signal -> remedies, cheapest first. Every ladder ends at NOVEL.
REMEDY_LADDER: dict[FailureSignal, list[Remedy]] = {
    FailureSignal.LOW_GLOBAL_CONFIDENCE: [
        _r("Deepen the MSA: add databases, relax the e-value, and check the returned depth "
           "rather than assuming the search succeeded.",
           RemedyTier.CHEAP,
           "Low global confidence with a shallow alignment is the textbook case, and an MSA "
           "search that silently returned few sequences looks identical to a hard target.",
           None, "pLDDT rises broadly, not just in one region."),
        _r("Increase recycles and add seeds, then check whether confidence rises or just varies.",
           RemedyTier.CHEAP,
           "Distinguishes an under-converged prediction from a genuinely uncertain one.",
           "structure-ensemble"),
        _r("Add structural templates from the Stage 1 family corpus.",
           RemedyTier.MODERATE,
           "Supplies the evolutionary signal the MSA could not, which is the remedy when the "
           "target's family is well characterised but its own sequence is not.",
           "template-and-finetune"),
        _r("Fine-tune on the family corpus with a curriculum, gated against held-out complexes.",
           RemedyTier.EXPENSIVE,
           "Worth it only when a curated corpus exists and templating was insufficient.",
           "template-and-finetune"),
        _r("Escalate to research: adjacent fields and the neglected literature for methods that "
           "handle low-homology targets.",
           RemedyTier.NOVEL,
           "The known ladder is exhausted; the remaining options are ones nobody here has tried.",
           "neglected-literature"),
    ],
    FailureSignal.LOW_POCKET_CONFIDENCE: [
        _r("Check whether the low-confidence region is a genuinely flexible loop by comparing "
           "against the holo structures in the graph.",
           RemedyTier.FREE,
           "A mobile loop with low pLDDT is the model being correct about uncertainty, not "
           "wrong. Treating it as failure produces a restraint that fights the biology.",
           "parts-inventory"),
        _r("Add templates chosen for pocket similarity rather than global fold.",
           RemedyTier.MODERATE,
           "Global templating can improve the fold and leave the site untouched; pocket-matched "
           "templates target the region that is actually uncertain.",
           "template-and-finetune"),
        _r("Impose pocket restraints from the Stage 2 interaction matrix, additively.",
           RemedyTier.MODERATE,
           "Uses measured contacts to constrain the region the model is unsure about. Additive "
           "only — a required restraint inverts on ligands that do not make that contact.",
           "pocket-anatomy"),
        _r("Escalate to research on site-specific conditioning.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "cross-domain-analogy"),
    ],
    FailureSignal.LOW_INTERFACE_CONFIDENCE: [
        _r("Confirm the intended biological assembly and that the partner chain is the right "
           "one, not another copy in the asymmetric unit.",
           RemedyTier.FREE,
           "Interface confidence against the wrong partner is meaningless. This project has "
           "already selected an RXR partner in place of the intended chain.",
           None),
        _r("Add seeds and check whether the interface varies or is consistently poor.",
           RemedyTier.CHEAP,
           "Separates an under-sampled interface from one the model cannot place.",
           "structure-ensemble"),
        _r("Template the complex from a homologous co-structure rather than the monomer.",
           RemedyTier.MODERATE,
           "An interface has to be templated as an interface; monomer templates do not "
           "constrain the relative orientation.",
           "template-and-finetune"),
        _r("Escalate to research on interface prediction for this complex class.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "neglected-literature"),
    ],
    FailureSignal.LOW_LIGAND_ACCURACY: [
        _r("Check the pose is being compared against the right reference and that ligand "
           "symmetry is handled, before concluding the pose is wrong.",
           RemedyTier.FREE,
           "A symmetric ligand scored without symmetry correction reports a large error for a "
           "correct pose. This is the single most common false failure in pose evaluation.",
           "harness-verification"),
        _r("Regenerate ligand conformers with a different generator and re-run.",
           RemedyTier.CHEAP,
           "Input conformer bias propagates into the predicted pose; a second generator tests "
           "whether the error came from the starting geometry.",
           "structure-ensemble"),
        _r("Widen the pool and measure the oracle gap before improving the model.",
           RemedyTier.CHEAP,
           "If a good pose is already in the pool, the problem is selection and no amount of "
           "better generation will show up in the score.",
           "bottleneck-triage",
           "A large oracle gap redirects the whole effort to selection."),
        _r("Add physics-based rescoring — strain, clashes, buriedness — as a challenger signal.",
           RemedyTier.MODERATE,
           "Confidence and physical plausibility fail differently, so a physics term can break "
           "ties confidence gets wrong. Test it against the confidence baseline rather than "
           "adopting it for being principled.",
           "physics-rescoring"),
        _r("Add a learned affinity or interface-quality rescorer, after checking it scores the "
           "candidate rather than the input it came from.",
           RemedyTier.MODERATE,
           "A rescorer that reads only the ligand identity ranks compounds, not poses, and will "
           "look useful on a benchmark where the two correlate.",
           "learned-rescoring"),
        _r("Fit a scoring function to this pocket specifically, using the Stage 2 interaction "
           "matrix and the family's known complexes.",
           RemedyTier.EXPENSIVE,
           "A general scorer is trained on the average pocket. Worth the cost only when the "
           "pocket is unusual and enough family complexes exist to fit against.",
           "budget-calibration"),
        _r("Escalate to research on pose prediction for this ligand class.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "neglected-literature"),
    ],
    FailureSignal.LIGAND_OUTSIDE_POCKET: [
        _r("Check whether the predicted protein is in an apo-like conformation with no pocket "
           "to place the ligand into.",
           RemedyTier.FREE,
           "The ligand is not misplaced — there is nowhere to put it. Fixing the pose without "
           "fixing the pocket is treating the symptom.",
           "parts-inventory"),
        _r("Seed the prediction from a holo structure of the target or a close homologue.",
           RemedyTier.MODERATE,
           "An induced-fit pocket has to be started from a bound conformation; models default "
           "to the apo state because that is what most training structures are.",
           "template-and-finetune"),
        _r("Dock into the predicted pocket with restraints instead of co-folding.",
           RemedyTier.MODERATE,
           "Separates the two problems: get the protein from folding, get the pose from docking.",
           "dock-and-minimize"),
        _r("Escalate to research on induced-fit co-folding.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "cross-domain-analogy"),
    ],
    FailureSignal.LIGAND_CLASHES: [
        _r("Check protonation and tautomer state, and whether hydrogens were added consistently "
           "with what the scorer expects.",
           RemedyTier.FREE,
           "Most apparent clashes are a protonation mismatch between the prediction and the "
           "clash check, not a geometry error.",
           None, "Clashes vanish rather than reduce."),
        _r("Minimise the pose in the pocket with a force field and re-score.",
           RemedyTier.CHEAP,
           "Resolves small steric strain without changing the binding mode. If the clash "
           "survives minimisation it is a real placement error.",
           "dock-and-minimize"),
        _r("Add a clash term to selection so clashing candidates lose to clean ones in the pool.",
           RemedyTier.MODERATE,
           "Cheaper than fixing generation when a clean candidate already exists.",
           "physics-rescoring"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.WRONG_STEREOCHEMISTRY: [
        _r("Round-trip the input SMILES and compare stereo descriptors before and after every "
           "step that touches the molecule.",
           RemedyTier.FREE,
           "Stereochemistry is lost silently by format conversion, and a lost stereocentre "
           "produces a confidently wrong pose that looks like a model failure.",
           None, "The corrected input fixes it outright."),
        _r("Enumerate stereoisomers and predict each, then select.",
           RemedyTier.CHEAP,
           "Correct when the input genuinely does not specify the configuration.",
           "structure-ensemble"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.POCKET_COLLAPSED: [
        _r("Check whether the target is known to be induced-fit before treating this as an error.",
           RemedyTier.FREE,
           "For an adaptable pocket the apo-like prediction is the expected default, not a "
           "malfunction, and the fix is conditioning rather than resampling.",
           "binder-census"),
        _r("Predict from an ensemble of holo templates spanning the observed pocket volume range.",
           RemedyTier.MODERATE,
           "Sizes the ensemble to the measured conformational range rather than to the "
           "best-resolution structure, which is the specific remedy for a promiscuous target.",
           "structure-ensemble"),
        _r("Fine-tune on holo complexes of the family so the bound conformation is the prior.",
           RemedyTier.EXPENSIVE,
           "Shifts the model's default from apo to holo. Expensive, and the right answer when "
           "templating repeatedly fails on the same target class.",
           "template-and-finetune"),
        _r("Escalate to research on conformational conditioning.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "neglected-literature"),
    ],
    FailureSignal.HIGH_SEED_VARIANCE: [
        _r("Check whether variance is concentrated in the pocket or spread across the model.",
           RemedyTier.FREE,
           "Spread variance means under-convergence; pocket-localised variance means the site "
           "is genuinely underdetermined, and the remedies differ.",
           None),
        _r("Add seeds and measure the oracle gap — high variance with a good best candidate is "
           "a selection problem, not a generation one.",
           RemedyTier.CHEAP,
           "Variance is only a failure if the selector cannot find the good candidate. This is "
           "the check that decides which half to work on.",
           "bottleneck-triage"),
        _r("Improve selection: normalise confidence within each generator, then take the "
           "per-item argmax.",
           RemedyTier.MODERATE,
           "With a fixed pool and no ground truth, selection usually decides the score outright.",
           "confidence-selection"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.CONSISTENT_BUT_WRONG: [
        _r("Confirm the reference is right before concluding the model is. Consistency across "
           "seeds plus a bad score is the signature of a wrong reference.",
           RemedyTier.FREE,
           "A model that agrees with itself and disagrees with the answer is either "
           "systematically biased or being graded against the wrong thing, and the second is "
           "free to check.",
           "harness-verification"),
        _r("Add a *decorrelated* generator — a different model family, not more seeds.",
           RemedyTier.CHEAP,
           "More seeds of a biased model reproduce the bias. Only a differently-wrong generator "
           "can put a right answer in the pool.",
           "generator-diversity",
           "The oracle gap opens up, which is what makes the failure recoverable."),
        _r("Rescue the tail: overwrite only the lowest-confidence items with the decorrelated "
           "generator's candidates, sweeping how many.",
           RemedyTier.MODERATE,
           "Over-replacement destroys good picks, so the count is swept rather than guessed.",
           "tail-rescue"),
        _r("Escalate to research: systematic bias is where a cross-domain analogy is most "
           "likely to help, because the in-field methods share the bias.",
           RemedyTier.NOVEL,
           "Every in-field method trained on the same structures may share the same blind spot.",
           "cross-domain-analogy"),
    ],
    FailureSignal.GOOD_POOL_BAD_PICK: [
        _r("Confirm the oracle gap with the same harness used for the headline number.",
           RemedyTier.FREE,
           "An oracle gap measured with a different metric is not the gap you can close.",
           "bottleneck-triage"),
        _r("Normalise confidence within each generator before comparing across them.",
           RemedyTier.CHEAP,
           "Cross-generator confidence is not commensurable, and comparing raw values silently "
           "prefers whichever model is most confident rather than most correct.",
           "score-normalization",
           "Most of the gap closes here, and it costs nothing."),
        _r("Find a confidence signal actually predictive of quality, scoped to the sub-object "
           "being scored, with a known-useless signal as a negative control.",
           RemedyTier.MODERATE,
           "A plausible signal that does not discriminate is worse than none, and the negative "
           "control is what proves the harness can tell the difference.",
           "signal-scoping"),
        _r("Add a challenger signal — physics or learned — and test it against the confidence "
           "baseline.",
           RemedyTier.MODERATE,
           "Beats the baseline or it does not; being principled is not evidence.",
           "physics-rescoring"),
        _r("Escalate to research on selection under no ground truth.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "neglected-literature"),
    ],
    FailureSignal.CONFIDENCE_UNCORRELATED: [
        _r("Check the signal is scoped to the thing being scored — a global confidence cannot "
           "rank poses of the same complex.",
           RemedyTier.FREE,
           "The commonest cause: a whole-model score used to rank candidates that share the "
           "model. It cannot discriminate because it does not vary with what is being chosen.",
           "signal-scoping"),
        _r("Measure discrimination directly with AUC, against a negative control.",
           RemedyTier.CHEAP,
           "Turns 'the signal seems not to work' into a number, and the control validates the "
           "measurement rather than the signal.",
           "signal-scoping"),
        _r("Replace or supplement with a challenger signal and compare on held-out items.",
           RemedyTier.MODERATE,
           "A selector more sophisticated than per-generator argmax is guilty until it beats it.",
           "learned-rescoring"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.METRIC_ARTEFACT: [
        _r("Run the identity test and the perturbation test on the harness.",
           RemedyTier.FREE,
           "A scorer that does not return a perfect score for a structure against itself is "
           "broken, and that is one call to find out.",
           "harness-verification",
           "Either the harness is exonerated or the failure was never real."),
        _r("Confirm the implemented metric is the one being graded on, including symmetry "
           "handling and units.",
           RemedyTier.FREE,
           "A convenient metric adopted in place of the official one produces a number that "
           "improves while the graded score does not.",
           "harness-verification"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.HARNESS_UNVERIFIED: [
        _r("Verify the harness before making any decision from a number it produced.",
           RemedyTier.FREE,
           "Every downstream conclusion inherits the harness's correctness, so this is the "
           "cheapest high-value check available and it gates everything else.",
           "harness-verification"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.HIGH_DOMAIN_PAE: [
        _r("Check whether the domains are genuinely flexibly linked, in which case a single "
           "orientation is the wrong output.",
           RemedyTier.FREE,
           "High inter-domain PAE on a hinged protein is correct uncertainty. Forcing one "
           "orientation discards information the model got right.",
           None),
        _r("Predict domains separately and assess the site within its own domain.",
           RemedyTier.CHEAP,
           "Domain orientation and pocket geometry are different questions; a bad answer to the "
           "first should not condemn a good answer to the second.",
           "structure-ensemble"),
        _r("Template the multi-domain arrangement from a homologue.",
           RemedyTier.MODERATE, "Supplies the orientation the model cannot infer.",
           "template-and-finetune"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
    FailureSignal.MISSING_REGION: [
        _r("Check whether the region is disordered — absence from the PDB is evidence of "
           "disorder, not of a modelling failure.",
           RemedyTier.FREE,
           "An unmodelled disordered tail is the correct output. Forcing a conformation onto it "
           "invents structure and then scores it.",
           None),
        _r("Confirm the missing region does not line the pocket before ignoring it.",
           RemedyTier.FREE,
           "A disordered region that contributes to the site changes the pocket definition and "
           "therefore every contact measured in it.",
           "parts-inventory"),
        _r("Escalate to research on disordered-region handling.",
           RemedyTier.NOVEL, "Known remedies exhausted.", "neglected-literature"),
    ],
    FailureSignal.IMPLAUSIBLE_INTERNAL_GEOMETRY: [
        _r("Check the strain is real and not an artefact of the force field or the protonation "
           "assumed by the scorer.",
           RemedyTier.FREE,
           "Strain terms are sensitive to parameterisation, and a mismatched force field "
           "reports strain for a reasonable geometry.",
           "physics-rescoring"),
        _r("Minimise in place and re-measure.",
           RemedyTier.CHEAP, "Distinguishes recoverable strain from a wrong conformer.",
           "dock-and-minimize"),
        _r("Filter on strain during selection rather than fixing generation.",
           RemedyTier.MODERATE,
           "Cheaper when a low-strain candidate already exists in the pool.",
           "physics-rescoring"),
        _r("Escalate to research.", RemedyTier.NOVEL, "Known remedies exhausted.", None),
    ],
}


def ladder_for(signal: FailureSignal, *, include_universal: bool = True) -> list[Remedy]:
    """Remedies for a signal, cheapest first, with the universal checks prepended.

    ``include_universal`` defaults to True because the three free checks apply to every signal
    and skipping them is the commonest way effort gets wasted here. Pass False only when they
    have already been run in this experiment.
    """
    base = list(UNIVERSAL_FIRST) if include_universal else []
    return base + REMEDY_LADDER.get(signal, [])


def signals_without_ladders() -> list[str]:
    """Failure signals with no registered remedies. Should always be empty; checked by CI."""
    return sorted(s.value for s in FailureSignal if s not in REMEDY_LADDER)


def ladder_problems() -> list[str]:
    """Ways the registry itself is malformed. Exercised by the test suite."""
    out: list[str] = []
    if missing := signals_without_ladders():
        out.append(f"failure signals with no remedy ladder: {missing}")
    for signal, remedies in REMEDY_LADDER.items():
        ranks = [r.tier.rank for r in remedies]
        if ranks != sorted(ranks):
            out.append(
                f"{signal.value}: remedies not ordered cheapest-first "
                f"({[r.tier.value for r in remedies]})"
            )
        if not remedies:
            out.append(f"{signal.value}: empty ladder")
            continue
        if remedies[-1].tier is not RemedyTier.NOVEL:
            out.append(
                f"{signal.value}: ladder does not end at NOVEL. Every ladder needs an escalation "
                "rung, because a registry presented as complete is the same failure as a search "
                "presented as exhaustive."
            )
        unknown = [r.via_skill for r in remedies if r.via_skill and "/" in (r.via_skill or "")]
        if unknown:
            out.append(f"{signal.value}: via_skill should be a skill name, got {unknown}")
    return out
