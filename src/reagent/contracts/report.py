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
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Re-exported so `from reagent.contracts.report import Evidence` keeps working.
from .axes import NeighborhoodSweep
from .discovery import SearchLedger
from .evidence import Confidence, Evidence
from .experiment import ExperimentLedger
from .followup import FollowUpTree
from .interpret import (
    Glossary,
    Interpretation,
    mean_sentence_length,
    undefined_jargon,
)
from .parts import Anatomy
from .reasoning import ReasoningTrace
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


class FindingKind(str, Enum):
    OBSERVATION = "observation"        # a fact read out of a source
    HYPOTHESIS = "hypothesis"          # a testable proposition we generated
    PRIOR = "prior"                    # a constraint to inject into modelling
    CONSTRAINT = "constraint"          # a hard requirement (e.g. valid PDB out)
    BENCHMARK = "benchmark"            # a number to beat / a baseline
    NEGATIVE = "negative_result"       # something that did NOT work
    DESIGN_CHOICE = "design_choice"    # a pipeline decision + rationale
    RISK = "risk"                      # a known failure mode


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

    interpretation: Interpretation | None = Field(
        default=None,
        description=(
            "What this means and what it changes. Required for the decision-bearing "
            "kinds (prior, design_choice, negative_result, constraint) because those "
            "are the ones a downstream stage acts on, and an uninterpreted one gets "
            "either ignored or misapplied."
        ),
    )

    follow_ups: FollowUpTree | None = Field(
        default=None,
        description=(
            "The questions this finding provokes, answered in place and nested up to five "
            "levels. Lets one report serve a specialist who opens nothing and a newcomer "
            "who opens everything, instead of splitting the difference and serving neither."
        ),
    )

    #: Kinds a downstream stage acts on, and which therefore must say what they mean.
    #: An uninterpreted observation is merely unhelpful; an uninterpreted prior gets
    #: applied outside its domain of validity, which is how a pipeline regresses.
    NEEDS_INTERPRETATION: ClassVar[frozenset[FindingKind]] = frozenset({
        FindingKind.PRIOR,
        FindingKind.DESIGN_CHOICE,
        FindingKind.NEGATIVE,
        FindingKind.CONSTRAINT,
    })

    @model_validator(mode="after")
    def _decision_bearing_findings_must_be_interpreted(self) -> Finding:
        if self.kind in Finding.NEEDS_INTERPRETATION and self.interpretation is None:
            raise ValueError(
                f"finding {self.id} is a {self.kind.value}, which a downstream stage "
                "will act on, so it needs an `interpretation`: what it means (including "
                "a layperson register) and what it changes. Without one it will be "
                "either ignored or applied outside the conditions it holds under."
            )
        return self

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
    plain_summary: str | None = Field(
        default=None,
        min_length=80,
        description=(
            "The same outcome for someone outside the field: what was asked, what came "
            "back, and why it matters, with no undefined jargon. This is the paragraph "
            "that decides whether a non-specialist can use the report at all, so "
            "`--strict` requires it and checks it against the glossary."
        ),
    )
    glossary: Glossary = Field(
        default_factory=Glossary,
        description=(
            "Run-level term definitions. Define a term once here and every finding's "
            "plain register may use it; the renderer makes them hoverable."
        ),
    )

    inputs: list[InputRef] = Field(default_factory=list)
    methods: list[MethodStep] = Field(default_factory=list)
    reasoning: ReasoningTrace = Field(
        default_factory=ReasoningTrace,
        description=(
            "How the agent decided, not what it ran. Records the options weighed, why "
            "one was chosen, and which sources informed the judgement — the trail that "
            "makes an analysis auditable rather than merely cited."
        ),
    )
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

    follow_ups: FollowUpTree | None = Field(
        default=None,
        description=(
            "Report-level disclosure tree, for the questions about the run as a whole "
            "rather than about one finding: why this approach, what would have changed the "
            "answer, what is still open."
        ),
    )
    search: SearchLedger | None = Field(
        default=None,
        description=(
            "What was searched, through which channels, and how much of the retrievable "
            "literature that plausibly represents. A retrieval stage without this is "
            "asserting thoroughness rather than reporting it."
        ),
    )
    sweep: NeighborhoodSweep | None = Field(
        default=None,
        description=(
            "Axis derivation and per-axis exhaustion, for stages that build a "
            "neighbourhood. Carries the record of which connections were considered at "
            "all — including the ones dismissed, which is the only way a reader can "
            "disagree with a boundary they cannot otherwise see."
        ),
    )
    experiments: ExperimentLedger | None = Field(
        default=None,
        description=(
            "Small experiments run during this stage: what was predicted before each one, what "
            "came back, and which remedy was tried when a prediction missed. This is the "
            "stage's memory — agents have none across sessions, so a remedy that plausibly "
            "should have worked and did not has to be written here or be rediscovered at full "
            "cost."
        ),
    )
    anatomy: Anatomy | None = Field(
        default=None,
        description=(
            "Stage 2's decomposition: every piece of the target, every piece of every test "
            "compound, and the interaction grid between them. The Stage 1 analogue of a "
            "`sweep` — where that recorded which relations were worked, this records which "
            "pieces were accounted for and which cells of the grid were actually measured."
        ),
    )

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

    # -- the interpretive layer ------------------------------------------

    def effective_glossary(self) -> Glossary:
        """Run glossary plus every term any finding introduced, deduplicated."""
        out = self.glossary
        for f in self.findings:
            if f.interpretation and f.interpretation.glossary:
                out = out.merge(f.interpretation.glossary)
        return out

    def plain_language_problems(self) -> list[str]:
        """Places a non-specialist would be stopped. Empty means the report reads.

        Checked against the *effective* glossary, so a term defined once for the run
        satisfies every finding that uses it.
        """
        defined = self.effective_glossary().defined()
        problems: list[str] = []

        if self.plain_summary:
            if jargon := undefined_jargon(self.plain_summary, defined):
                problems.append(
                    "plain_summary uses undefined jargon: "
                    + ", ".join(repr(j) for j in jargon)
                )
            avg = mean_sentence_length(self.plain_summary)
            if avg > 32:
                problems.append(
                    f"plain_summary averages {avg:.0f} words per sentence; aim under 25"
                )

        for f in self.findings:
            if f.interpretation is None:
                continue
            for p in f.interpretation.check_plain_language(defined):
                problems.append(f"{f.id}: {p}")

        # A definition written in more undefined jargon has moved the problem, not
        # solved it, and leaves the reader exactly where they started.
        for term, leftover in self.effective_glossary().circular_definitions().items():
            problems.append(
                f"glossary term {term!r} is defined using jargon nothing explains: "
                + ", ".join(repr(x) for x in leftover)
            )
        return problems

    def knowledge_telling_findings(self) -> dict[str, list[str]]:
        """Findings whose interpretation restates rather than explains.

        The failure this detects is the default behaviour of any explainer, human or
        model: producing a more fluent version of the input and stopping there. Kept
        separate from `plain_language_problems` because the two failures are opposite —
        one is prose that is too hard to read, this one is prose that reads well and says
        nothing new.
        """
        out: dict[str, list[str]] = {}
        for f in self.findings:
            if f.interpretation is None:
                continue
            if probs := f.interpretation.knowledge_building_problems():
                out[f.id] = probs
        return out

    def uninterpreted_findings(self) -> list[str]:
        """Findings with no interpretation. Fatal only for the decision-bearing kinds,
        which the Finding validator already enforces; the rest is advisory."""
        return [f.id for f in self.findings if f.interpretation is None]

    def findings_without_implications(self) -> list[str]:
        """Interpreted findings that change nothing downstream — candidate trivia."""
        return [
            f.id for f in self.findings
            if f.interpretation is not None and not f.interpretation.implications
        ]

    def implications_by_stage(self) -> dict[str, list[tuple[str, str]]]:
        """``{stage: [(finding_id, decision)]}`` — what this report asks of each stage.

        This is what a downstream owner should read first: not the whole report, but
        the list of decisions it claims to bear on.
        """
        out: dict[str, list[tuple[str, str]]] = {}
        for f in self.findings:
            if not f.interpretation:
                continue
            for imp in f.interpretation.implications:
                out.setdefault(imp.for_stage, []).append((f.id, imp.decision))
        return out

    # -- progressive disclosure -------------------------------------------

    def follow_up_problems(self) -> list[str]:
        """Places the reader's trail runs out. Advisory; `--strict` promotes these.

        Checked against the *effective* glossary plus whatever each tree defines for
        itself, so a term defined once for the run does not need re-explaining in every
        branch that mentions it.
        """
        defined = self.effective_glossary().defined()
        out: list[str] = []
        if self.follow_ups:
            out += [f"report follow-ups: {p}" for p in self.follow_ups.problems(defined)]
        for f in self.findings:
            if f.follow_ups:
                out += [f"{f.id} follow-ups: {p}" for p in f.follow_ups.problems(defined)]
        return out

    def findings_without_follow_ups(self) -> list[str]:
        """Decision-bearing findings a reader cannot drill into.

        Advisory rather than fatal, because not every finding provokes a question. But a
        `prior` or `design_choice` that nobody can interrogate is being asked to be taken
        on trust, which is the opposite of what this project is for.
        """
        return [
            f.id for f in self.findings
            if f.kind in Finding.NEEDS_INTERPRETATION and f.follow_ups is None
        ]

    def disclosure_depth(self) -> dict[str, int]:
        """Deepest disclosure level per finding. A report of all-depth-1 trees has
        anticipated the first question and none of the ones its answers provoke."""
        out = {f.id: f.follow_ups.depth() for f in self.findings if f.follow_ups}
        if self.follow_ups:
            out["__report__"] = self.follow_ups.depth()
        return out

    # -- search coverage --------------------------------------------------

    def coverage_problems(self) -> list[str]:
        """Ways the retrieval behind this report is not yet auditable.

        Separate from every other check because it is about what is *absent*. A missing
        source leaves no trace in the report that cites the ones we found, so the only
        defence is to make the shape of the search itself reportable.
        """
        out: list[str] = []
        if self.search:
            out += [f"search: {p}" for p in self.search.problems()]
        if self.sweep:
            out += [f"sweep: {p}" for p in self.sweep.problems()]
        if self.anatomy:
            out += [f"anatomy: {p}" for p in self.anatomy.problems()]
        if self.experiments:
            out += [f"experiments: {p}" for p in self.experiments.problems()]
        return out

    def learned_this_run(self) -> dict[str, dict[str, list[str]]]:
        """What the experiments established, split into what worked and what did not.

        The second half is the more valuable one and the half nobody records: a remedy that
        sounds right and does not work is the expensive thing to rediscover.
        """
        if self.experiments is None:
            return {}
        return {
            "worked": self.experiments.what_worked(),
            "did_not_work": self.experiments.what_did_not(),
        }

    def anatomy_coverage(self) -> dict[str, float]:
        """Stage 2's three completeness numbers, or empty when there is no anatomy.

        Reported together because they fail independently: a run can account for every atom
        of every compound and still have measured one corner of the interaction grid.
        """
        if self.anatomy is None:
            return {}
        a = self.anatomy
        cells = [m.cell_coverage for m in a.matrices]
        return {
            "target_parts": round(a.target_inventory.coverage, 3),
            "test_batch": round(a.batch_coverage(), 3),
            "matrix_cells": round(sum(cells) / len(cells), 3) if cells else 0.0,
        }

    def neglected_sources(self) -> list[tuple[str, list[str]]]:
        """Cited sources flagged as under-attended, with why. Feeds the report's
        "what we found that the field mostly hasn't" section."""
        out: list[tuple[str, list[str]]] = []
        seen: set[str] = set()
        for f in self.findings:
            for e in f.evidence:
                if e.is_neglected and e.locator not in seen:
                    seen.add(e.locator)
                    out.append((e.locator, [r.value for r in e.neglect]))
        return out

    def discovery_channel_mix(self) -> dict[str, float]:
        """Share of admitted sources per channel, from the ledger if present.

        Concentration is the warning: if one channel found everything, the others were
        configured rather than run.
        """
        return self.search.channel_mix() if self.search else {}

    def audience_coverage(self) -> dict[str, int]:
        """How many findings speak to each audience register."""
        counts: dict[str, int] = {}
        for f in self.findings:
            if not f.interpretation:
                continue
            for a in f.interpretation.for_audience:
                counts[a.value] = counts.get(a.value, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def reasoning_gaps(self) -> list[str]:
        """Where the reasoning trail is thin. Advisory; `--strict` promotes these."""
        problems: list[str] = []
        steps = self.reasoning.steps
        if not steps:
            problems.append(
                "no reasoning steps recorded — the report says what was concluded but "
                "not how, so a reader cannot tell which choices were made or what was "
                "rejected"
            )
            return problems

        ids = [f.id for f in self.findings]
        orphans = self.reasoning.orphan_findings(ids)
        if ids and len(orphans) > len(ids) / 2:
            problems.append(
                f"{len(orphans)} of {len(ids)} findings trace to no recorded decision "
                f"({orphans[:6]}) — most of the reasoning path is unrecorded"
            )
        if uncited := self.reasoning.uncited_steps():
            problems.append(
                f"{len(uncited)} decisions cite no source at all: {uncited[:6]}. "
                "Say what informed the judgement, or that nothing did."
            )
        return problems

    def reasoning_sources(self) -> list[str]:
        """Sources that informed the agent's judgement, distinct from claim evidence."""
        return self.reasoning.all_sources()

    def unvisualized_metrics(self) -> list[str]:
        """Headline metrics that no figure shows. A number nobody can see is a claim.

        Primarily reads each figure's declared ``covers_metrics``. A text fallback
        catches the case where an author populated the captions but not the
        declaration — it is deliberately generous, because a false "this is
        unvisualized" warning is more annoying than a missed one, and the declaration
        is the mechanism we actually want people to use.
        """
        if self.visuals is None:
            return list(self.metrics)

        declared: set[str] = set()
        for v in self.visuals.visualizations:
            declared.update(v.covers_metrics)

        remaining = [k for k in self.metrics if k not in declared]
        if not remaining:
            return []

        haystack = " ".join(
            f"{v.question} {v.takeaway} {' '.join(v.encoding.values())} "
            f"{' '.join(str(x) for x in v.params.values())}"
            for v in self.visuals.visualizations
        ).lower()
        # Match on the metric's meaningful words, ignoring a leading count prefix,
        # so `n_fold_neighbours` is satisfied by a caption saying "fold neighbours".
        def shown(key: str) -> bool:
            words = [w for w in key.lower().lstrip("n_").split("_") if len(w) > 2]
            return bool(words) and all(w in haystack for w in words)

        return [k for k in remaining if not shown(k)]

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
