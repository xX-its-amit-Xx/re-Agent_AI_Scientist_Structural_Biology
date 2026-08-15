"""Model Report — the single artifact every pipeline stage must emit.

A stage is only "done" when it has written a validated ModelReport. Downstream
stages read *reports*, never each other's internals, so Denny (Stage 2) and
Sumer (Stage 3) can work without coordinating on file layout.

Two invariants carry most of the weight here:

1.  Every Finding carries Evidence, and every Evidence carries a resolvable
    locator. A claim with no locator cannot be checked by the next agent, so
    the validator rejects it.
2.  Evidence borrowed from outside structural biology (the cross-domain
    analogy engine) is a distinct SourceType and can never raise a Finding
    above ``Confidence.SPECULATIVE`` on its own. An analogy is a reason to run
    an experiment, not a result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .viz import EXPECTED_VIZ, VizBundle, missing_expected

SCHEMA_VERSION = "1.0.0"


class Stage(str, Enum):
    """Pipeline stages. Stage 0 is the meta-innovation scouting pass."""

    SCOUTING = "stage0_scouting"
    LITERATURE = "stage1_literature"
    BIOCHEM = "stage2_biochem"
    PRIOR = "stage3_prior"
    OPTIMIZATION = "stage4_optimization"
    SYNTHESIS = "synthesis"


class SourceType(str, Enum):
    """Where a piece of evidence came from.

    The ordering is deliberate: everything at or below ``ANALOGY`` is
    *ungrounded* with respect to the biology and is capped in confidence.
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
    # Frequently the only public record of a negative result, a parameter choice,
    # or a practitioner default. Lower-trust, not no-trust: still grounded, but
    # `Confidence.ESTABLISHED` needs a second independent source anyway.
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
        silently fails on a class of input is real evidence about the world. What
        is *not* grounded is a mechanism borrowed from another field, or a
        teammate's hunch.
        """
        return self not in {SourceType.ANALOGY, SourceType.EXPERT_PRIOR}

    @property
    def is_grey(self) -> bool:
        """Unreviewed sources. Usable, but never sufficient alone for 'established'."""
        return self in {
            SourceType.BLOG, SourceType.SOCIAL, SourceType.DOCS,
            SourceType.TALK, SourceType.COMPETITION,
        }


class Confidence(str, Enum):
    ESTABLISHED = "established"    # multiple independent grounded sources
    SUPPORTED = "supported"        # one solid grounded source
    TENTATIVE = "tentative"        # weak/indirect grounded support
    SPECULATIVE = "speculative"    # hypothesis, analogy-derived, untested

    @property
    def rank(self) -> int:
        return {"speculative": 0, "tentative": 1, "supported": 2, "established": 3}[self.value]


class FindingKind(str, Enum):
    OBSERVATION = "observation"        # a fact read out of a source
    HYPOTHESIS = "hypothesis"          # a testable proposition we generated
    PRIOR = "prior"                    # a constraint to inject into modelling
    CONSTRAINT = "constraint"          # a hard requirement (e.g. valid PDB out)
    BENCHMARK = "benchmark"            # a number to beat / a baseline
    NEGATIVE = "negative_result"       # something that did NOT work
    DESIGN_CHOICE = "design_choice"    # a pipeline decision + rationale
    RISK = "risk"                      # a known failure mode


class Evidence(BaseModel):
    """One resolvable pointer backing a Finding."""

    source_type: SourceType
    locator: str = Field(
        ...,
        description=(
            "A resolvable identifier: DOI, PMID, PDB ID, ChEMBL ID, UniProt "
            "accession, patent number, NCT number, URL, or for COMPUTATION a "
            "repo-relative path to the artifact that produced it."
        ),
    )
    title: str | None = None
    excerpt: str | None = Field(
        default=None,
        description="Verbatim supporting span. Do not paraphrase here — paraphrase in the finding.",
    )
    year: int | None = None
    # For ANALOGY evidence only: the source domain it was lifted from.
    source_domain: str | None = None

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
                "(e.g. 'quantitative finance') so it is never mistaken for biology"
            )
        return self


class Finding(BaseModel):
    """A single claim the stage is willing to stand behind."""

    id: str = Field(..., description="Stable within a report, e.g. 'F-LIT-014'.")
    kind: FindingKind
    statement: str = Field(..., min_length=10, description="One assertion, in plain prose.")
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)
    # Free-form structured payload so a downstream agent can act without NLP.
    data: dict[str, Any] = Field(default_factory=dict)
    # Which KG nodes this finding touches, so the graph and report stay in sync.
    kg_nodes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_grounding(self) -> Finding:
        # A design choice or risk may be asserted by the agent itself; an
        # observation about the world may not.
        needs_evidence = {
            FindingKind.OBSERVATION,
            FindingKind.BENCHMARK,
            FindingKind.NEGATIVE,
            FindingKind.PRIOR,
        }
        if self.kind in needs_evidence and not self.evidence:
            raise ValueError(
                f"finding {self.id} is a {self.kind.value} and must cite at least one Evidence"
            )

        grounded = [e for e in self.evidence if e.source_type.is_grounded]

        # The anti-laundering rule: if a finding *does* cite sources but none of
        # them are grounded in the problem domain, it is an analogy wearing a
        # citation. A finding with no evidence at all is a different thing — the
        # agent's own reasoning — and is allowed up to 'supported' for the kinds
        # that do not require citations.
        if self.evidence and not grounded and self.confidence.rank > Confidence.SPECULATIVE.rank:
            raise ValueError(
                f"finding {self.id} cites only ungrounded evidence "
                f"({[e.source_type.value for e in self.evidence]}) so it cannot be "
                f"'{self.confidence.value}' — cap it at 'speculative' until something "
                "in the problem domain supports it"
            )
        if self.confidence is Confidence.ESTABLISHED:
            if len({e.locator for e in grounded}) < 2:
                raise ValueError(
                    f"finding {self.id} claims 'established' but cites fewer than two "
                    "independent grounded sources"
                )
            if all(e.source_type.is_grey for e in grounded):
                raise ValueError(
                    f"finding {self.id} claims 'established' on grey literature alone "
                    f"({[e.source_type.value for e in grounded]}). Grey sources are "
                    "legitimate evidence — a blog post or GitHub issue is often the only "
                    "record of a negative result — but 'established' needs at least one "
                    "reviewed or structured-database source. Use 'supported' instead."
                )
        return self


class Artifact(BaseModel):
    """A file this stage produced that someone downstream will open."""

    path: str = Field(..., description="Repo-relative path.")
    kind: str = Field(..., description="e.g. 'kg-nodes', 'pdb', 'figure', 'csv', 'notebook'.")
    description: str
    sha256: str | None = None
    bytes: int | None = None

    def stamp(self, repo_root: Path) -> Artifact:
        """Fill in size and hash from disk. Returns self for chaining."""
        p = repo_root / self.path
        if p.is_file():
            raw = p.read_bytes()
            self.sha256 = hashlib.sha256(raw).hexdigest()
            self.bytes = len(raw)
        return self


class MethodStep(BaseModel):
    """One tool invocation, recorded so the run can be replayed or costed."""

    skill: str = Field(..., description="Skill name from skills/registry.json.")
    tool: str | None = Field(default=None, description="Concrete tool/CLI/API called.")
    summary: str
    params: dict[str, Any] = Field(default_factory=dict)
    n_calls: int = 1
    wall_seconds: float | None = None
    cost_usd: float | None = None
    credits: str | None = Field(
        default=None, description="Which credit pool this spent, e.g. 'boltz', 'modal'."
    )
    failed: bool = False
    failure_note: str | None = None


class InputRef(BaseModel):
    """Something this stage consumed."""

    kind: Literal["report", "kg", "file", "dataset", "decision"]
    locator: str
    note: str | None = None


class Handoff(BaseModel):
    """The explicit contract with the next stage.

    This is the part a teammate reads first. Keep it blunt.
    """

    to_stage: Stage
    ready: bool = Field(..., description="False means: do not build on this yet.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable handoff, keyed by the schema the next stage expects.",
    )
    recommended_actions: list[str] = Field(default_factory=list)
    blocking_unknowns: list[str] = Field(
        default_factory=list,
        description="Things the next stage must resolve or route around.",
    )


class AgentIdentity(BaseModel):
    model: str = Field(default="unknown", description="e.g. 'claude-fable-5'.")
    skill: str | None = None
    harness: str = Field(default="claude-code")
    human_owner: str | None = Field(default=None, description="Which teammate owns this stage.")


class ModelReport(BaseModel):
    """The stage deliverable. Validated, versioned, and diffable."""

    schema_version: str = SCHEMA_VERSION
    report_id: str = Field(..., description="e.g. 'stage1-literature-2026-08-15a'.")
    run_id: str = Field(..., description="Groups reports from one end-to-end run.")
    stage: Stage
    title: str
    created_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    produced_by: AgentIdentity = Field(default_factory=AgentIdentity)

    objective: str = Field(..., min_length=10, description="What this stage was asked to do.")
    executive_summary: str = Field(
        ..., min_length=30, description="What a reader needs if they read nothing else."
    )

    inputs: list[InputRef] = Field(default_factory=list)
    methods: list[MethodStep] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    visuals: VizBundle | None = Field(
        default=None,
        description=(
            "Required in practice: a stage must SHOW its result. See `require_visuals` "
            "on the validator and reagent.contracts.viz for the rationale."
        ),
    )
    handoff: Handoff | None = None

    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Headline numbers, e.g. {'n_proteins': 42}."
    )
    limitations: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(
        default_factory=list, description="Ledger entries (accept/deny) this stage acted on."
    )

    @field_validator("findings")
    @classmethod
    def _unique_finding_ids(cls, v: list[Finding]) -> list[Finding]:
        seen: set[str] = set()
        for f in v:
            if f.id in seen:
                raise ValueError(f"duplicate finding id: {f.id}")
            seen.add(f.id)
        return v

    @model_validator(mode="after")
    def _must_say_something(self) -> ModelReport:
        if not self.findings and not self.limitations:
            raise ValueError(
                "a report with no findings must at least record why "
                "(populate `limitations`) — silent empty reports break the chain"
            )
        return self

    # -- convenience ----------------------------------------------------

    def visual_gaps(self) -> list[str]:
        """Advisory: characteristic figures this stage did not produce.

        Kept advisory rather than fatal so an early exploratory run is not blocked,
        but `reagent report validate --strict` promotes these to errors, and that
        is what CI and the orchestrator use before a stage is allowed to hand off.
        """
        if self.visuals is None:
            return [
                f"no visuals at all — {self.stage.value} should show "
                f"{[k.value for k in EXPECTED_VIZ.get(self.stage.value, [])]}"
            ]
        return [k.value for k in missing_expected(self.stage.value, self.visuals)]

    def unvisualized_metrics(self) -> list[str]:
        """Headline metrics that no figure reads from. A number nobody can see is a claim."""
        if self.visuals is None:
            return list(self.metrics)
        mentioned = " ".join(
            f"{v.question} {v.takeaway} {' '.join(v.encoding.values())}"
            for v in self.visuals.visualizations
        ).lower()
        return [k for k in self.metrics if k.lower().replace("_", " ") not in mentioned
                and k.lower() not in mentioned]

    def grounded_findings(self) -> list[Finding]:
        return [
            f for f in self.findings
            if any(e.source_type.is_grounded for e in f.evidence)
        ]

    def by_kind(self, kind: FindingKind) -> list[Finding]:
        return [f for f in self.findings if f.kind is kind]

    def total_cost_usd(self) -> float:
        return sum(m.cost_usd or 0.0 for m in self.methods)

    def write(self, path: Path) -> Path:
        """Persist as JSON. Creates parent dirs."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> ModelReport:
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def json_schema() -> dict[str, Any]:
    """Exported for teammates working in other languages / for doc generation."""
    return ModelReport.model_json_schema()
