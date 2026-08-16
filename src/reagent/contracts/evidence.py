"""Evidence primitives, shared by everything that cites something.

Extracted from ``report.py`` because two modules need them and importing them from
``report`` created a cycle: ``reasoning.py`` cites sources for a *judgement*, while
``report.py`` cites sources for a *claim*, and both need the same ``Evidence`` type.

``report.py`` re-exports these names, so existing imports keep working.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from reagent.contracts.discovery import AttentionProfile, DiscoveryChannel, NeglectReason


class SourceType(str, Enum):
    """Where a piece of evidence came from.

    The ordering is deliberate: everything at or below ``ANALOGY`` is *ungrounded*
    with respect to the problem domain and is capped in confidence.
    """

    # -- peer-reviewed / formal ------------------------------------------
    PAPER = "paper"
    PREPRINT = "preprint"
    PATENT = "patent"
    CLINICAL_TRIAL = "clinical_trial"
    REGULATORY = "regulatory_doc"
    THESIS = "thesis"
    # -- structured data -------------------------------------------------
    STRUCTURE = "structure"          # PDB / CIF entry
    DATABASE = "database"            # UniProt, ChEMBL, BindingDB, Pharos, ...
    DATASET = "dataset"              # Zenodo, Figshare, HuggingFace, OSF deposit
    CODE_REPO = "code_repo"          # GitHub/GitLab — often the only place a detail lives
    COMPETITION = "competition"      # Kaggle / benchmark challenge writeups and data
    # -- grey literature -------------------------------------------------
    # Frequently the only public record of a negative result, a parameter choice, or a
    # practitioner default. Lower-trust, not no-trust.
    BLOG = "blog"                    # lab blogs, Substack, company engineering posts
    SOCIAL = "social"                # LinkedIn / X / forum / Discord recap
    DOCS = "documentation"           # tool docs, issue trackers, release notes
    TALK = "talk"                    # conference talk, poster, recorded seminar
    # -- our own work ----------------------------------------------------
    COMPUTATION = "computation"      # something we ran ourselves
    BENCHMARK = "benchmark"          # leaderboard / held-out eval result
    # -- ungrounded ------------------------------------------------------
    ANALOGY = "cross_domain_analogy"  # finance, cybersec, art, ecology, ...
    EXPERT_PRIOR = "expert_prior"    # a human on the team asserted it

    @property
    def is_grounded(self) -> bool:
        """Whether this source says anything about the problem domain itself.

        Grey literature counts as grounded — a GitHub issue reporting that a tool
        silently fails on a class of input is real evidence about the world. What is
        *not* grounded is a mechanism borrowed from another field, or a hunch.
        """
        return self not in {SourceType.ANALOGY, SourceType.EXPERT_PRIOR}

    @property
    def is_grey(self) -> bool:
        """Unreviewed sources. Usable, but never sufficient alone for 'established'.

        ``CODE_REPO`` counts as grey even though it sits in the structured-data block
        above, because the thing being cited is usually a claim in a README or an issue
        rather than a measurement. A repository's *data* is a `DATASET`; a repository's
        *assertion about its own performance* is grey, and treating a self-reported
        benchmark as consensus is exactly the mistake this guards.
        """
        return self in {
            SourceType.BLOG, SourceType.SOCIAL, SourceType.DOCS,
            SourceType.TALK, SourceType.COMPETITION, SourceType.CODE_REPO,
        }


class Confidence(str, Enum):
    ESTABLISHED = "established"    # multiple independent grounded sources
    SUPPORTED = "supported"        # one solid grounded source
    TENTATIVE = "tentative"        # weak/indirect grounded support
    SPECULATIVE = "speculative"    # hypothesis, analogy-derived, untested

    @property
    def rank(self) -> int:
        return {"speculative": 0, "tentative": 1, "supported": 2, "established": 3}[self.value]


class Evidence(BaseModel):
    """One resolvable pointer, backing either a claim or a judgement."""

    source_type: SourceType
    locator: str = Field(
        ...,
        description=(
            "A resolvable identifier: DOI, PMID, PDB ID, ChEMBL ID, UniProt accession, "
            "patent number, NCT number, URL, or for COMPUTATION a repo-relative path to "
            "the artifact that produced it."
        ),
    )
    title: str | None = None
    excerpt: str | None = Field(
        default=None,
        description="Verbatim supporting span. Do not paraphrase here — paraphrase in the claim.",
    )
    year: int | None = None
    # For ANALOGY evidence only: the source domain it was lifted from.
    source_domain: str | None = None

    # -- how we came to have this, and why it was easy or hard to find ------
    found_via: DiscoveryChannel | None = Field(
        default=None,
        description=(
            "Which discovery channel surfaced this. Required for coverage estimation: "
            "without it, 'we searched thoroughly' cannot be checked, only asserted."
        ),
    )
    neglect: list[NeglectReason] = Field(
        default_factory=list,
        description=(
            "Why this source has less attention than its relevance warrants. Empty is the "
            "normal case. Each entry must be backed by a signal in `attention` or by "
            "`neglect_justification` — see the validator."
        ),
    )
    attention: AttentionProfile | None = None
    neglect_justification: str | None = Field(
        default=None,
        description=(
            "Prose argument for the neglect reasons that no bibliometric field can "
            "establish. Must name the specific mechanism, not assert being ahead of its time."
        ),
    )

    @field_validator("locator")
    @classmethod
    def _locator_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("evidence.locator must be a resolvable identifier, not blank")
        return v.strip()

    @model_validator(mode="after")
    def _analogy_needs_domain(self) -> Evidence:
        if self.source_type is SourceType.ANALOGY and not self.source_domain:
            raise ValueError(
                "cross_domain_analogy evidence must name its source_domain "
                "(e.g. 'quantitative finance') so it is never mistaken for domain evidence"
            )
        return self

    @model_validator(mode="after")
    def _neglect_claims_are_backed(self) -> Evidence:
        """A neglect reason must rest on a signal or an argument, never on narrative.

        This is the load-bearing guard for the ``neglected-literature`` skill. Hunting for
        under-attended work is worth doing and is also the easiest thing in this project to
        fake, because "few citations, but ahead of its time" fits every paper ever written.
        Requiring either a bibliometric signal or a named mechanism is what separates
        recovering a neglected result from laundering an irrelevant one.
        """
        if not self.neglect:
            return self

        probe = self.attention or AttentionProfile()
        prose_only = probe.needs_written_justification

        unbacked = [
            r.value for r in self.neglect
            if r not in prose_only and not (self.attention and self.attention.supports(r))
        ]
        if unbacked:
            raise ValueError(
                f"neglect reason(s) {unbacked} claimed for {self.locator} without a "
                "supporting signal in `attention`. These reasons are bibliometric and must "
                "be evidenced: "
                + "; ".join(NeglectReason(r).note for r in unbacked)
            )

        needs_prose = [r.value for r in self.neglect if r in prose_only]
        if needs_prose and not (self.neglect_justification or "").strip():
            raise ValueError(
                f"neglect reason(s) {needs_prose} for {self.locator} cannot be established "
                "from citation data — they require `neglect_justification` naming the "
                "specific mechanism. Without it this is an assertion that the work is "
                "underrated, which is available for any work at all."
            )
        return self

    @property
    def is_neglected(self) -> bool:
        return bool(self.neglect)
