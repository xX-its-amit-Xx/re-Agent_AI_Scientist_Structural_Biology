"""Interpretation — what a finding *means*, to whom, and what it changes.

A finding with a citation is checkable. It is not necessarily *understandable*, and
it does not by itself tell anyone what to do differently. Those are separate
obligations, and a report that meets only the first one is the failure mode this
module exists to prevent:

    "PXR shares SHARES_MOTIF with CYP3A4 (score 0.59, speculative)."

That is precise, cited, queryable — and conveys nothing to a reader who does not
already know why it would matter. The interpretive layer adds three things:

**Why it is so.** ``mechanism`` — the causal account. Not the evidence for the claim
but the reason the world is that way. A reader who has the mechanism can predict the
next case; a reader with only the correlation cannot.

**What it means, per audience.** A medicinal chemist, a structural biologist, an ML
practitioner, and a non-specialist each need a different sentence about the same
fact. ``for_audience`` carries all of them, and the layperson register is
**required** — if a fact cannot be explained to someone outside the field, that is
usually a sign the author does not understand it either.

**What it changes.** ``implications`` name a downstream stage, the decision it bears
on, and which way it argues. A fact with no implication is trivia; a report full of
trivia is why pipeline design usually happens by intuition instead of from evidence.

The plain-language register is enforced mechanically, not encouraged. Undefined
jargon in ``plain`` is a validation error, because "write for a layperson" as a
prompt instruction reliably produces jargon with a friendlier tone.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Audience(str, Enum):
    """Who a sentence is written for.

    These are registers, not difficulty levels. A structural biologist and a
    medicinal chemist looking at the same shared motif genuinely see different
    things — one sees a fold constraint, the other sees a pharmacophore — and
    flattening them into one "expert" voice loses the more useful half.
    """

    LAYPERSON = "layperson"
    MEDICINAL_CHEMIST = "medicinal_chemist"
    STRUCTURAL_BIOLOGIST = "structural_biologist"
    ML_PRACTITIONER = "ml_practitioner"
    CLINICIAN = "clinician"


class ImplicationStrength(str, Enum):
    DECISIVE = "decisive"        # on its own this settles the decision
    STRONG = "strong"            # would need a good reason to go against it
    SUGGESTIVE = "suggestive"    # tips the balance
    WEAK = "weak"                # worth knowing, does not move the decision


#: Directional verbs and phrases an `Implication.direction` must contain.
#:
#: Deliberately excludes a bare "for", which made an earlier version of this check
#: trivially passable: "relevant for template selection" satisfied it while taking no
#: position at all.
#:
#: Module level, not a class attribute: pydantic treats a leading-underscore class
#: attribute as a private attribute, so `_DIRECTIONAL` inside the model became a
#: ModelPrivateAttr and every direction was rejected.
DIRECTIONAL = re.compile(
    r"\b(argues?|arguing|favours?|favors?|supports?|opposes?|prefers?|"
    r"recommends?|advises?|warrants?|justifies|rules?\s+out|"
    r"avoid|include|exclude|adopt|drop|keep|discard|"
    r"increases?|decreases?|raises?|lowers?|widens?|narrows?|tightens?|"
    r"for\s+(including|excluding|using|adopting|running|weighting|dropping|keeping)|"
    r"against|in\s+favour\s+of|in\s+favor\s+of|toward|away\s+from)\b",
    re.I,
)


class Implication(BaseModel):
    """What a finding changes downstream, stated so it can be acted on or refused."""

    for_stage: str = Field(
        ...,
        description=(
            "Stage value this bears on, e.g. 'stage3_prior'. Use 'all' if general. "
            "Note that several skills share a stage, so `for_stage` cannot route to a "
            "skill — put that in `decision`."
        ),
    )
    decision: str = Field(
        ...,
        min_length=10,
        description=(
            "The concrete decision affected — 'which structures to use as templates', "
            "'whether to weight the fine-tuning corpus by receptor'. Not a topic."
        ),
    )
    direction: str = Field(
        ...,
        min_length=15,
        description=(
            "Which way this argues, and why. 'Argues FOR including CYP structures in "
            "the template set, because they share the adaptable-pocket problem even "
            "though they do not share the fold.'"
        ),
    )
    strength: ImplicationStrength = ImplicationStrength.SUGGESTIVE
    if_wrong: str = Field(
        ...,
        min_length=15,
        description=(
            "What goes wrong downstream if this interpretation is mistaken. This is the "
            "field that makes an implication reviewable rather than merely assertive."
        ),
    )

    @field_validator("for_stage")
    @classmethod
    def _stage_must_exist(cls, v: str) -> str:
        """A typo'd stage addresses an implication to nobody, and `stages_affected()`
        would report it as real. Validated here rather than typed as the enum so 'all'
        stays expressible."""
        from .report import Stage

        valid = {s.value for s in Stage} | {"all"}
        if v not in valid:
            raise ValueError(
                f"for_stage {v!r} is not a stage. Use one of {sorted(valid)} — an "
                "implication addressed to a stage that does not exist will never be read."
            )
        return v

    @field_validator("direction")
    @classmethod
    def _must_take_a_side(cls, v: str) -> str:
        if not DIRECTIONAL.search(v):
            raise ValueError(
                "`direction` does not take a side. Say what this argues FOR or AGAINST "
                "using a directional verb — argues for, argues against, favours, rules "
                "out, include, exclude, raise, lower. An implication that merely names a "
                "topic as 'relevant' cannot change a decision, and 'relevant for X' is "
                "the phrasing this check exists to reject."
            )
        return v


class GlossaryTerm(BaseModel):
    """One piece of jargon, defined once and reused across the run."""

    term: str
    plain: str = Field(
        ...,
        min_length=20,
        description="One or two sentences a non-specialist can follow. No other jargon.",
    )
    why_it_matters: str = Field(
        ...,
        min_length=20,
        description="Why a reader of THIS report needs the term at all.",
    )
    aliases: list[str] = Field(default_factory=list)
    analogy: str | None = Field(
        default=None,
        description=(
            "An everyday comparison, if one genuinely helps. A bad analogy is worse "
            "than none, because the reader remembers the analogy and not the fact."
        ),
    )

    def jargon_in_definition(self, also_defined: set[str] | None = None) -> list[str]:
        """Jargon inside this term's own definition.

        A definition written in three more undefined terms is not a definition — it is
        a redirect. Advisory rather than fatal, because a definition sometimes must
        reference a sibling term that the same glossary defines; pass the rest of the
        glossary as ``also_defined`` and only genuinely unexplained words remain.
        """
        allowed = {self.term, *self.aliases} | (also_defined or set())
        return undefined_jargon(self.plain, allowed)


#: Terms that make a sentence unreadable to a non-specialist. Anything here appearing
#: in a ``plain`` register must be defined in the glossary.
#:
#: Seeded for structural biology, cheminformatics, and machine learning because that
#: is the reference domain; extend per domain rather than deleting entries. Kept as
#: word-boundary patterns so "fold" the verb does not trip "fold" the noun — see
#: ``undefined_jargon`` for how ambiguous words are handled.
JARGON = {
    # structural biology
    "ligand-binding domain", "lbd", "apo", "holo", "co-crystal", "cocrystal",
    "allosteric", "orthosteric", "pharmacophore", "pocket volume", "b-factor",
    "plddt", "pae", "iptm", "ptm", "rmsd", "tm-score", "lddt", "lddt-pli",
    "backbone", "sidechain", "side-chain", "helix", "beta-sheet", "loop region",
    "superposition", "superpose", "conformer", "conformational", "protonation",
    "isoform", "paralog", "ortholog", "homolog", "homologue", "pfam", "interpro",
    "nuclear receptor", "transcription factor", "coactivator", "corepressor",
    "residue", "motif", "fold", "domain", "epitope", "hydrophobic", "hydrophilic",
    "salt bridge", "pi-stacking", "halogen bond", "van der waals", "hydrogen bond",
    "solvent-exposed", "buried", "cryptic pocket", "induced fit",
    # chemistry
    "scaffold", "murcko", "tanimoto", "morgan fingerprint", "ecfp", "smiles",
    "inchi", "chemotype", "congeneric", "moiety", "functional group", "heteroatom",
    "aromatic", "aliphatic", "stereochemistry", "chirality", "enantiomer",
    "tautomer", "logp", "logd", "pka", "admet", "adme", "pharmacokinetic",
    "bioavailability", "clearance", "efficacy", "potency", "affinity", "ic50",
    "ec50", "kd", "ki", "agonist", "antagonist", "inverse agonist", "partial agonist",
    "promiscuous", "polypharmacology", "xenobiotic", "cytochrome p450", "cyp",
    "induction", "substrate", "metabolite", "warhead", "linker", "ring system",
    "fragment", "lead compound", "series",
    # machine learning
    "co-folding", "cofolding", "ensemble", "oracle", "held-out", "cross-validation",
    "overfit", "overfitting", "distribution shift", "domain shift", "out-of-distribution",
    "embedding", "latent", "sparse autoencoder", "sae", "fine-tune", "fine-tuning",
    "checkpoint", "inference", "logit", "calibration", "auroc", "auc", "spearman",
    "pearson", "z-score", "normalisation", "normalization", "hyperparameter",
    "msa", "multiple sequence alignment", "template", "sampling", "seed",
}

#: Words in JARGON that are also ordinary English. Flagged only when they appear in a
#: technical collocation, so "the way the protein folds" passes and "a shared fold"
#: does not. Without this the check fires constantly and gets switched off.
#: Each entry is (label, pattern). The pattern must require enough context to
#: distinguish the technical sense, or the check fires on ordinary prose and gets
#: switched off — which is worse than not having it.
AMBIGUOUS = {
    # Bare articles are deliberately excluded from every pattern below. Including
    # them ("the template", "an ensemble") makes the check fire on ordinary prose —
    # note that this project's own phrase "the domain of validity" would trip a
    # pattern that accepted "the domain".
    # Both word orders: "a shared fold" and "the fold is conserved".
    "fold": (
        "fold",
        r"\b(its|shared|same|similar|common|conserved)\s+fold\b"
        r"|\bfold\s+(similarity|space)\b"
        r"|\bfolds?\s+(is|are|was|were)\s+(conserved|shared|similar|preserved|the\s+same)\b",
    ),
    "domain": ("domain", r"\b(binding|protein|ligand|catalytic|structural)\s+domains?\b"),
    "motif": ("motif", r"\b(structural|sequence|shared|binding|conserved)\s+motifs?\b"),
    "residue": ("residue", r"\b(pocket|lining|conserved|key|critical|anchor)\s+residues?\b"),
    "series": ("series", r"\bchemical\s+series\b|\bcongeneric\s+series\b"),
    "template": (
        "template",
        r"\bstructural\s+templates?\b|\btemplates?\s+(set|selection|transfer)\b"
        r"|\bas\s+a\s+template\b",
    ),
    # "seed" and "buried" are everyday words; only the technical collocations count.
    "seed": ("seed", r"\b(random|model|per)[ -]seeds?\b|\bseeds?\s+per\b|\b\d+\s+seeds?\b"),
    "buried": ("buried", r"\bburied\s+(surface|residues?|area|fraction)\b|\bsolvent[- ]buried\b"),
    "ensemble": (
        "ensemble",
        r"\b(model|conformer|structural)\s+ensembles?\b"
        r"|\bensembles?\s+(of models|method|prediction|selection)\b",
    ),
    "affinity": ("affinity", r"\b(binding|measured)\s+affinit(y|ies)\b"),
}


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9\s\-]", " ", text.lower())


def undefined_jargon(text: str, defined: set[str]) -> list[str]:
    """Jargon in ``text`` that ``defined`` does not cover.

    ``defined`` should hold lower-cased terms and aliases from the glossary. Matching
    is on word boundaries, longest term first, so defining "ligand-binding domain"
    also satisfies the bare "domain" inside it.
    """
    hay = _normalise(text)
    known = {d.lower().strip() for d in defined}

    # Blank out defined terms so their component words stop matching.
    for term in sorted(known, key=len, reverse=True):
        if term:
            hay = re.sub(rf"\b{re.escape(term)}\b", " ", hay)

    hits: list[str] = []
    for term in sorted(JARGON, key=len, reverse=True):
        if term in known:
            continue
        if term in AMBIGUOUS:
            _label, pattern = AMBIGUOUS[term]
            if re.search(pattern, hay):
                hits.append(term)
                hay = re.sub(pattern, " ", hay)
            continue
        # Match a simple plural too: the lexicon stores singular forms, so without
        # this "chemotypes" sails past an entry for "chemotype".
        pattern = rf"\b{re.escape(term)}(?:s|es)?\b"
        if re.search(pattern, hay):
            hits.append(term)
            hay = re.sub(pattern, " ", hay)
    return sorted(set(hits))


def mean_sentence_length(text: str) -> float:
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


class Interpretation(BaseModel):
    """Why a finding matters, to whom, and what it changes downstream."""

    mechanism: str | None = Field(
        default=None,
        description=(
            "The causal account: WHY the world is this way, not the evidence that it "
            "is. A reader with the mechanism can predict the next case."
        ),
    )
    for_audience: dict[Audience, str] = Field(
        ...,
        description=(
            "One sentence or short paragraph per audience register. "
            "Audience.LAYPERSON is required and is checked for undefined jargon."
        ),
    )
    implications: list[Implication] = Field(
        default_factory=list,
        description="What this changes downstream. A finding with none is trivia.",
    )
    glossary: list[GlossaryTerm] = Field(
        default_factory=list,
        description=(
            "Terms this finding introduces. Prefer the run-level glossary on the "
            "report for anything used more than once."
        ),
    )
    analogy: str | None = Field(
        default=None,
        description="An everyday comparison, only if it genuinely clarifies.",
    )
    caveat_for_reader: str | None = Field(
        default=None,
        description=(
            "The misreading a reader is most likely to make. Naming it is often more "
            "valuable than the finding, because it is what stops the finding being "
            "over-applied."
        ),
    )

    @model_validator(mode="after")
    def _layperson_register_is_required_and_plain(self) -> Interpretation:
        plain = self.for_audience.get(Audience.LAYPERSON, "").strip()
        if not plain:
            raise ValueError(
                "Interpretation.for_audience must include Audience.LAYPERSON. If a "
                "finding cannot be explained to someone outside the field, that is "
                "usually a sign it is not yet understood well enough to act on."
            )
        if len(plain) < 40:
            raise ValueError(
                f"the layperson register is {len(plain)} characters, which is too short "
                "to explain anything. Say what it is and why it matters."
            )
        return self

    def check_plain_language(self, extra_defined: set[str] | None = None) -> list[str]:
        """Problems with the layperson register. Empty list means it reads plainly.

        Returned rather than raised so a report-level validator can attach the
        run-wide glossary before judging — a term defined once for the whole report
        should not have to be redefined on every finding that uses it.
        """
        plain = self.for_audience.get(Audience.LAYPERSON, "")
        defined = {t.term for t in self.glossary}
        for t in self.glossary:
            defined.update(t.aliases)
        defined |= (extra_defined or set())

        problems: list[str] = []
        if jargon := undefined_jargon(plain, defined):
            problems.append(
                "the layperson register uses undefined jargon: "
                + ", ".join(repr(j) for j in jargon)
                + ". Either define each term in the glossary or rewrite without it — "
                "a plain register with jargon in it is not plain, it is just friendlier."
            )
        avg = mean_sentence_length(plain)
        if avg > 32:
            problems.append(
                f"the layperson register averages {avg:.0f} words per sentence, over the "
                "32-word limit. Long sentences are the other way a plain register fails; "
                "aim under 25, which leaves room for the occasional longer one."
            )
        return problems

    def audiences_covered(self) -> list[str]:
        return sorted(a.value for a in self.for_audience)

    def stages_affected(self) -> list[str]:
        return sorted({i.for_stage for i in self.implications})


class Glossary(BaseModel):
    """Run-level term definitions, so jargon is explained once and linked everywhere."""

    terms: list[GlossaryTerm] = Field(default_factory=list)

    def defined(self) -> set[str]:
        out: set[str] = set()
        for t in self.terms:
            out.add(t.term)
            out.update(t.aliases)
        return out

    def get(self, term: str) -> GlossaryTerm | None:
        low = term.lower()
        for t in self.terms:
            if t.term.lower() == low or low in {a.lower() for a in t.aliases}:
                return t
        return None

    def merge(self, other: Glossary | list[GlossaryTerm]) -> Glossary:
        incoming = other.terms if isinstance(other, Glossary) else other
        have = {t.term.lower() for t in self.terms}
        return Glossary(terms=[*self.terms, *(t for t in incoming if t.term.lower() not in have)])

    def missing_for(self, text: str) -> list[str]:
        """Jargon in ``text`` this glossary does not cover."""
        return undefined_jargon(text, self.defined())

    def circular_definitions(self) -> dict[str, list[str]]:
        """Terms whose own definitions use jargon nothing in this glossary explains.

        Run this before shipping. A glossary that defines "promiscuous" as "exhibits
        polypharmacology" has moved the problem rather than solved it, and the reader
        is no better off than before.
        """
        all_defined = self.defined()
        out: dict[str, list[str]] = {}
        for t in self.terms:
            if leftover := t.jargon_in_definition(all_defined):
                out[t.term] = leftover
        return out
