"""Discovery channels, neglect reasons, and coverage estimation.

The asymmetry that justifies this module: **a recall failure is unrecoverable and a
precision failure is not.** A source you never retrieved cannot be down-weighted later,
re-read, or argued with — it is simply absent, and nothing downstream can tell the
difference between "we considered it and rejected it" and "we never saw it". A source
retrieved wrongly, by contrast, gets filtered by the verification gate at known cost.

That asymmetry is why the harvest stage runs at high recall and low precision, and why the
question "what did we miss?" needs a real answer rather than a reassurance.

Three things are recorded here.

``DiscoveryChannel``
    *How* a source was found. Needed for two reasons. Coverage estimation by
    capture-recapture requires knowing which channel found what, and it is the only way to
    notice that one channel is doing all the work — in a well-known audit of a review of
    complex evidence, protocol-driven database search accounted for a minority of the
    primary sources actually used, with citation chaining and personal knowledge supplying
    most of the rest.

``NeglectReason``
    *Why* a relevant source accumulated little attention. Citation count measures
    accumulated attention, and attention accrues by a rich-get-richer process only loosely
    coupled to relevance. Recording the reason keeps "under-cited" from being treated as
    either a defect or a virtue.

``CoverageEstimate``
    A capture-recapture estimate of how much of the retrievable literature was actually
    retrieved, with its assumptions stated — because the way this estimator fails is by
    *overstating* coverage, which is the direction that tells you to stop early.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DiscoveryChannel(str, Enum):
    """How a source came to our attention.

    Channels are grouped by whether they are *pull* (we described what we wanted) or
    *push*/*traversal* (the literature's own structure led us there). The distinction
    matters because pull channels can only return things whose vocabulary we already
    guessed, which is the failure mode traversal channels do not share.
    """

    # -- pull: we specified the query -----------------------------------
    KEYWORD_SEARCH = "keyword_search"          # full-text or title/abstract query
    SEMANTIC_SEARCH = "semantic_search"        # embedding / vector similarity
    STRUCTURED_QUERY = "structured_query"      # database field query (RCSB, ChEMBL, ...)
    ONTOLOGY_EXPANSION = "ontology_expansion"  # MeSH/InterPro term expansion of a query

    # -- traversal: the literature's structure led us there --------------
    BACKWARD_SNOWBALL = "backward_snowball"    # references of a known-relevant paper
    FORWARD_SNOWBALL = "forward_snowball"      # papers citing a known-relevant paper
    CO_CITATION = "co_citation"                # cited alongside something relevant
    AUTHOR_TRAIL = "author_trail"              # other work by a relevant author
    VENUE_SWEEP = "venue_sweep"                # scanning a journal or proceedings volume

    # -- inference: nothing pointed at it; we deduced it should exist ----
    GRAPH_GAP = "graph_gap"                    # a two-hop path in our KG with no direct edge
    ANALOGY_TRANSFER = "analogy_transfer"      # a cross-domain mechanism suggested looking

    # -- outside the indexed record --------------------------------------
    GREY_CHANNEL = "grey_channel"              # repo, blog, forum, competition writeup
    REGIONAL_INDEX = "regional_index"          # non-English or regional bibliographic index
    REPOSITORY = "repository"                   # institutional repository, thesis archive
    HUMAN_POINTER = "human_pointer"            # a person told us

    @property
    def is_pull(self) -> bool:
        """Pull channels can only return what our vocabulary already anticipated."""
        return self in {
            DiscoveryChannel.KEYWORD_SEARCH,
            DiscoveryChannel.SEMANTIC_SEARCH,
            DiscoveryChannel.STRUCTURED_QUERY,
            DiscoveryChannel.ONTOLOGY_EXPANSION,
        }

    @property
    def is_traversal(self) -> bool:
        return self in {
            DiscoveryChannel.BACKWARD_SNOWBALL,
            DiscoveryChannel.FORWARD_SNOWBALL,
            DiscoveryChannel.CO_CITATION,
            DiscoveryChannel.AUTHOR_TRAIL,
            DiscoveryChannel.VENUE_SWEEP,
        }


class NeglectReason(str, Enum):
    """Why a relevant source has little accumulated attention.

    Each value corresponds to a distinct detection strategy in the
    ``neglected-literature`` skill. The point of enumerating them is that **no single
    proxy identifies neglected relevance** — a low citation count is compatible with all
    of these and with plain irrelevance, so the reason has to be established, not assumed.
    """

    TOO_RECENT = "too_recent"                  # citations have not had time to accrue
    SMALL_FIELD = "small_field"                # few possible citers exist at all
    HIGH_QUALITY_CITERS = "high_quality_citers"  # few citations, but from work that matters
    SLEEPING_BEAUTY = "sleeping_beauty"        # long dormancy, now accelerating
    INTERDISCIPLINARY_ORPHAN = "interdisciplinary_orphan"  # too far from any field's core
    NEGATIVE_RESULT = "negative_result"        # nulls are systematically under-cited
    LANGUAGE_BARRIER = "language_barrier"      # not in the English-language index
    NOT_INDEXED = "not_indexed"                # thesis, tech report, pre-digital, venue gap
    PREMATURELY_ABANDONED = "prematurely_abandoned"  # dropped for a reason no longer true
    LOW_AMPLIFICATION = "low_amplification"    # small group, no institutional megaphone
    VOCABULARY_MISMATCH = "vocabulary_mismatch"  # says the same thing in other words
    NEVER_STATED = "never_stated"              # the connection exists in no single paper

    @property
    def note(self) -> str:
        return {
            "too_recent": "Age-normalise before comparing; raw counts are uninformative.",
            "small_field": "Normalise within field and year, never against a global baseline.",
            "high_quality_citers": "Examine who cites it, not how many. A citation from "
                                   "work the field builds on is not one unit of attention.",
            "sleeping_beauty": "Look for acceleration after dormancy, and for the paper "
                               "that awakened it.",
            "interdisciplinary_orphan": "Search the union of two literatures for work that "
                                        "references both; neither field's core will cite it.",
            "negative_result": "Query explicitly for nulls and failures. These are the "
                               "highest-value findings for pipeline design and the most "
                               "systematically missing.",
            "language_barrier": "Search regional indexes with translated terms.",
            "not_indexed": "Route to grey channels and repositories.",
            "prematurely_abandoned": "Find why it was dropped, then test whether that "
                                     "reason still holds. Compute cost and data "
                                     "availability both expire.",
            "low_amplification": "Do not filter on venue or institutional prestige.",
            "vocabulary_mismatch": "Re-query in each field's own dialect, not ours.",
            "never_stated": "No search finds this; it is a graph query over two literatures.",
        }[self.value]


class AttentionProfile(BaseModel):
    """How much attention a source has accumulated, and in what shape.

    This exists to defend against the failure mode of the skill that uses it. A search
    deliberately hunting under-cited work will cheerfully rationalise junk — "few
    citations, but ahead of its time" is available for literally any paper. The defence is
    to require that a claimed ``NeglectReason`` be backed by a signal in this profile
    rather than by narrative. ``supports()`` is what enforces it.

    Every field is optional because bibliometric coverage is patchy, and an absent field
    is honest. What is *not* allowed is asserting a reason whose supporting field is absent.
    """

    n_citations: int | None = Field(default=None, ge=0)
    year: int | None = None
    as_of_year: int | None = Field(
        default=None, description="Year the citation count was taken, so it can age gracefully."
    )
    field_percentile: float | None = Field(
        default=None, ge=0.0, le=100.0,
        description=(
            "Citation percentile within field AND year. The only comparison that means "
            "anything — a raw count compares a 2025 structural-biology paper against a "
            "1998 methods paper and calls the difference quality."
        ),
    )
    field_size_note: str | None = Field(
        default=None,
        description="How many papers could plausibly have cited this. Small field, small ceiling.",
    )
    notable_citers: list[str] = Field(
        default_factory=list,
        description=(
            "Identifiers of high-relevance works that cite this one. A single citation "
            "from work the field is built on is not one unit of attention; it is a "
            "different kind of signal entirely."
        ),
    )
    dormancy_years: int | None = Field(
        default=None, ge=0,
        description="Years between publication and the first sustained citation activity.",
    )
    awakened_by: str | None = Field(
        default=None, description="The work whose attention revived this one, if identifiable."
    )
    citation_trend: str | None = Field(
        default=None, description="e.g. 'flat 2009-2019, 4x since 2023'."
    )
    language: str | None = None
    indexed_in: list[str] = Field(default_factory=list)
    not_indexed_in: list[str] = Field(default_factory=list)

    @property
    def age_years(self) -> int | None:
        if self.year is None or self.as_of_year is None:
            return None
        return max(0, self.as_of_year - self.year)

    @property
    def citations_per_year(self) -> float | None:
        age = self.age_years
        if self.n_citations is None or age is None:
            return None
        # A paper in its first year has had a fraction of a year to accumulate; treating
        # age as at least 1 avoids reporting an inflated rate from a tiny denominator.
        return self.n_citations / max(1, age)

    def supports(self, reason: NeglectReason) -> bool:
        """Whether this profile actually contains a signal for the claimed reason."""
        match reason:
            case NeglectReason.TOO_RECENT:
                age = self.age_years
                return age is not None and age <= 3
            case NeglectReason.SMALL_FIELD:
                return bool(self.field_size_note) or self.field_percentile is not None
            case NeglectReason.HIGH_QUALITY_CITERS:
                return bool(self.notable_citers)
            case NeglectReason.SLEEPING_BEAUTY:
                return self.dormancy_years is not None and self.dormancy_years >= 5 and bool(
                    self.citation_trend or self.awakened_by
                )
            case NeglectReason.LANGUAGE_BARRIER:
                return bool(self.language) and self.language.lower() not in {"en", "english"}
            case NeglectReason.NOT_INDEXED:
                return bool(self.not_indexed_in)
            case _:
                # The remaining reasons are argued from content rather than bibliometrics:
                # an interdisciplinary orphan, a negative result, a premature abandonment,
                # a vocabulary mismatch, a connection never stated. Those are established by
                # reading the thing, and the skill requires a written justification instead.
                return True

    @property
    def needs_written_justification(self) -> frozenset[NeglectReason]:
        """Reasons that no bibliometric field can establish — they must be argued in prose."""
        return frozenset({
            NeglectReason.INTERDISCIPLINARY_ORPHAN,
            NeglectReason.NEGATIVE_RESULT,
            NeglectReason.PREMATURELY_ABANDONED,
            NeglectReason.LOW_AMPLIFICATION,
            NeglectReason.VOCABULARY_MISMATCH,
            NeglectReason.NEVER_STATED,
        })

    def summary(self) -> str:
        bits: list[str] = []
        if self.n_citations is not None:
            s = f"{self.n_citations} citations"
            if (rate := self.citations_per_year) is not None:
                s += f" ({rate:.1f}/yr)"
            bits.append(s)
        if self.field_percentile is not None:
            bits.append(f"{self.field_percentile:.0f}th pctile in field-year")
        if self.notable_citers:
            bits.append(f"cited by {len(self.notable_citers)} high-relevance work(s)")
        if self.dormancy_years:
            bits.append(f"dormant {self.dormancy_years}y")
        if self.citation_trend:
            bits.append(self.citation_trend)
        if self.language and self.language.lower() not in {"en", "english"}:
            bits.append(f"language: {self.language}")
        return " · ".join(bits) if bits else "no bibliometric data"


class ChannelYield(BaseModel):
    """What one discovery channel actually produced."""

    channel: DiscoveryChannel
    n_retrieved: int = Field(..., ge=0, description="Candidates this channel surfaced.")
    n_admitted: int = Field(
        ..., ge=0, description="Candidates that survived verification and entered the graph."
    )
    n_unique: int = Field(
        default=0, ge=0,
        description=(
            "Admitted sources *no other channel* found. This is the number that justifies "
            "keeping a channel: a channel with high yield but zero unique finds is "
            "redundant, however productive it looks."
        ),
    )
    queries: list[str] = Field(
        default_factory=list, description="Verbatim queries or traversal seeds, for replay."
    )
    cost_note: str | None = None

    @model_validator(mode="after")
    def _counts_are_consistent(self) -> ChannelYield:
        if self.n_admitted > self.n_retrieved:
            raise ValueError(
                f"{self.channel.value}: admitted {self.n_admitted} exceeds retrieved "
                f"{self.n_retrieved}"
            )
        if self.n_unique > self.n_admitted:
            raise ValueError(
                f"{self.channel.value}: unique {self.n_unique} exceeds admitted "
                f"{self.n_admitted} — a source cannot be uniquely found and not admitted"
            )
        return self

    @property
    def precision(self) -> float:
        return self.n_admitted / self.n_retrieved if self.n_retrieved else 0.0


class CoverageEstimate(BaseModel):
    """Capture-recapture estimate of how much retrievable literature was retrieved.

    Two channels are treated as two independent "captures" of the same population. With
    ``n1`` found by the first, ``n2`` by the second, and ``m`` by both, the Chapman
    bias-corrected Lincoln-Petersen estimator gives the population size.

    **The way this fails matters more than the number.** The estimator assumes the two
    channels are independent and that every source is equally catchable. Both assumptions
    fail in literature search — channels tend to find the same *easy* sources — which
    inflates the overlap, shrinks the population estimate, and therefore **overstates
    coverage.** The bias points toward telling you that you are finished when you are not.
    So treat the estimate as an upper bound on coverage, and prefer channel pairs that are
    as mechanically different as possible: a keyword query and a citation traversal, not
    two keyword queries.
    """

    channel_a: DiscoveryChannel
    channel_b: DiscoveryChannel
    n_a: int = Field(..., ge=0, description="Relevant sources found by A.")
    n_b: int = Field(..., ge=0, description="Relevant sources found by B.")
    n_both: int = Field(..., ge=0, description="Found by both.")
    n_total_observed: int = Field(
        ..., ge=0, description="Distinct relevant sources found by any channel."
    )

    @model_validator(mode="after")
    def _overlap_is_possible(self) -> CoverageEstimate:
        if self.n_both > min(self.n_a, self.n_b):
            raise ValueError(
                f"overlap {self.n_both} exceeds the smaller channel "
                f"({min(self.n_a, self.n_b)}), which is arithmetically impossible"
            )
        if self.n_total_observed < max(self.n_a, self.n_b):
            raise ValueError(
                f"total observed {self.n_total_observed} is below the larger channel "
                f"({max(self.n_a, self.n_b)})"
            )
        return self

    @property
    def estimated_population(self) -> float | None:
        """Chapman bias-corrected estimate. None when the channels do not overlap at all."""
        if self.n_a == 0 or self.n_b == 0:
            return None
        if self.n_both == 0:
            # Disjoint captures give no basis for extrapolation — the estimator diverges.
            return None
        return ((self.n_a + 1) * (self.n_b + 1) / (self.n_both + 1)) - 1

    @property
    def coverage(self) -> float | None:
        """Observed fraction of the estimated population. Read as an *upper* bound."""
        pop = self.estimated_population
        if pop is None or pop <= 0:
            return None
        return min(1.0, self.n_total_observed / pop)

    @property
    def channels_are_mechanically_different(self) -> bool:
        """Whether the pair is a defensible basis for an estimate.

        Two pull channels share the vocabulary assumption, so their errors are correlated
        and the estimate is optimistic by construction.
        """
        return not (self.channel_a.is_pull and self.channel_b.is_pull)

    def summary(self) -> str:
        pop, cov = self.estimated_population, self.coverage
        lines = [
            f"Coverage estimate from {self.channel_a.value} x {self.channel_b.value}",
            f"  found by A: {self.n_a} · by B: {self.n_b} · by both: {self.n_both}",
            f"  distinct observed: {self.n_total_observed}",
        ]
        if pop is None:
            lines.append(
                "  no estimate possible: the channels did not overlap, so there is no "
                "basis for extrapolation. That is itself informative — disjoint channels "
                "mean the population is probably much larger than either found."
            )
        else:
            lines.append(f"  estimated retrievable population: {pop:.0f}")
            lines.append(f"  estimated coverage: {cov:.0%}  (read as an UPPER bound)")
        if not self.channels_are_mechanically_different:
            lines.append(
                "  WARNING: both channels are pull channels, so they share the vocabulary "
                "assumption. Their errors are correlated, the overlap is inflated, and "
                "this coverage figure is optimistic. Re-estimate against a traversal "
                "channel."
            )
        return "\n".join(lines)


class SearchLedger(BaseModel):
    """The complete record of what was searched, how, and what it produced.

    This is what makes "did we miss anything?" answerable rather than rhetorical. It is
    also the accounting for the exploration quota — the fraction of effort deliberately
    spent away from the well-cited core, which exists to counter the tendency of a
    self-referential graph to converge on the literature's existing hubs.
    """

    run_id: str
    channels: list[ChannelYield] = Field(default_factory=list)
    coverage: list[CoverageEstimate] = Field(default_factory=list)
    exploration_quota: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description=(
            "Fraction of retrieval effort spent deliberately on low-attention regions. A "
            "quota rather than a preference, because the alternative converges on hubs."
        ),
    )
    exploration_spent: float = Field(default=0.0, ge=0.0, le=1.0)
    saturation_note: str | None = Field(
        default=None,
        description=(
            "Why the search stopped. Must reference an observed quantity — a discovery "
            "curve flattening, a quota exhausted, a budget cap — and never model "
            "confidence, since models grow more confident as they grow more uniform."
        ),
    )
    known_gaps: list[str] = Field(
        default_factory=list,
        description=(
            "Regions deliberately not searched, named so the omission is visible. An "
            "unrecorded gap is indistinguishable from a claim of completeness."
        ),
    )

    def total_admitted(self) -> int:
        return sum(c.n_admitted for c in self.channels)

    def channel_mix(self) -> dict[str, float]:
        """Share of admitted sources per channel. Concentration here is the warning sign."""
        total = self.total_admitted()
        if not total:
            return {}
        return {
            c.channel.value: round(c.n_admitted / total, 3)
            for c in sorted(self.channels, key=lambda x: -x.n_admitted)
        }

    def redundant_channels(self) -> list[str]:
        """Channels that found nothing another channel did not. Candidates for removal."""
        return [c.channel.value for c in self.channels if c.n_admitted and not c.n_unique]

    def problems(self) -> list[str]:
        """Ways this search is not yet defensible."""
        out: list[str] = []
        if not self.channels:
            out.append("no channels recorded — the search is unauditable")
            return out

        used = {c.channel for c in self.channels if c.n_retrieved}
        if not any(ch.is_traversal for ch in used):
            out.append(
                "no traversal channel was used. Pull channels only return what our "
                "vocabulary anticipated, so a search without citation chaining or an "
                "author trail has an unmeasured blind spot in exactly the region where "
                "terminology differs from ours."
            )
        mix = self.channel_mix()
        if mix and max(mix.values()) > 0.8:
            top = max(mix, key=mix.get)
            out.append(
                f"{mix[top]:.0%} of admitted sources came from a single channel ({top}). "
                "One channel doing all the work means the others were not really tried."
            )
        if redundant := self.redundant_channels():
            out.append(
                f"channel(s) {redundant} admitted sources but found nothing another channel "
                "had not. Volume is not contribution: a channel with no unique finds is "
                "paying for results you already had, and next run should replace it with "
                "one whose failure mode differs."
            )
        if not self.coverage:
            out.append(
                "no coverage estimate — without one, 'we searched thoroughly' is an "
                "assertion. Pair a pull channel with a traversal channel and estimate."
            )
        else:
            optimistic = [c for c in self.coverage if not c.channels_are_mechanically_different]
            if optimistic and len(optimistic) == len(self.coverage):
                out.append(
                    "every coverage estimate pairs two pull channels, which inflates "
                    "overlap and overstates coverage in the direction that says stop early"
                )
        if self.exploration_quota and self.exploration_spent < self.exploration_quota * 0.8:
            out.append(
                f"exploration quota was {self.exploration_quota:.0%} but only "
                f"{self.exploration_spent:.0%} was spent — the quota exists precisely "
                "because it is the first thing dropped under time pressure"
            )
        if not self.saturation_note:
            out.append("no stated reason for stopping the search")
        if not self.known_gaps:
            out.append(
                "no known gaps recorded. Every real search has regions it did not reach; "
                "not naming them reads as a claim of completeness."
            )
        return out

    def summary(self) -> str:
        lines = [
            f"Search ledger for {self.run_id}",
            f"  {len(self.channels)} channels · {self.total_admitted()} admitted sources",
        ]
        for ch, share in self.channel_mix().items():
            yielded = next(c for c in self.channels if c.channel.value == ch)
            lines.append(
                f"    {ch:<22} {share:>6.1%}  ({yielded.n_admitted}/{yielded.n_retrieved} "
                f"admitted, {yielded.n_unique} unique)"
            )
        if redundant := self.redundant_channels():
            lines.append(f"  redundant (no unique finds): {redundant}")
        for est in self.coverage:
            lines.append("  " + est.summary().replace("\n", "\n  "))
        if self.exploration_quota:
            lines.append(
                f"  exploration quota {self.exploration_quota:.0%}, "
                f"spent {self.exploration_spent:.0%}"
            )
        if self.saturation_note:
            lines.append(f"  stopped because: {self.saturation_note}")
        if self.known_gaps:
            lines.append("  known gaps:")
            lines += [f"    - {g}" for g in self.known_gaps]
        if probs := self.problems():
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
