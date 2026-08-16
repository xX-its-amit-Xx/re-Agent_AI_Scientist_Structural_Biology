"""Progressive disclosure: the answers to the questions a reader will ask next.

The problem this solves is a real tension. A report that explains everything inline is
unreadable, and a report that explains nothing is unusable — and which one a given reader
needs depends entirely on what they already know. Writing for "an intelligent
non-specialist" splits the difference and satisfies nobody, because there is no single
depth at which a medicinal chemist and a software engineer both want to read.

So depth becomes the reader's choice rather than the author's. The top level stays short
enough to skim. Every term or claim that a reader might not accept at face value carries a
nested disclosure holding the answer, and those nest up to five levels — far enough that
someone starting with no background can keep opening until they hit something they already
know.

**The completeness rule, which is what makes this more than a nice widget.** An answer may
use an unexplained term only if a child follow-up explains that term. Recursively. So the
tree is finished exactly when every unexplained term either appears in the glossary or is
the subject of a child. That converts "write for a layman" — an instruction which
reliably produces jargon in a friendlier register — into a mechanical property of a data
structure, and it means the reader's click always lands somewhere.

The corollary is a hard cap. If jargon must be explained by a child, and children bottom
out at depth five, then the deepest level cannot introduce new jargon at all. That is not a
limitation of the format; it is what "keep opening until you reach something you know"
requires in order to terminate.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from reagent.contracts.evidence import Evidence
from reagent.contracts.interpret import mean_sentence_length, undefined_jargon

#: Maximum nesting. Five is the user-facing contract: a reader with no background should
#: be able to keep opening disclosures five times and land on something they already know.
MAX_DEPTH = 5

#: Soft word budget for an answer, by depth. Upper levels must be skimmable; deeper levels
#: are read deliberately by someone who chose to go there, so they may be longer.
#: These are advisory (reported by ``problems()``) rather than validation errors, because a
#: genuinely irreducible explanation should not be truncated to satisfy a counter.
WORD_BUDGET: dict[int, int] = {1: 60, 2: 90, 3: 120, 4: 150, 5: 200}


class FollowUpKind(str, Enum):
    """What kind of question this is. Drives ordering and the icon in the rendered tree."""

    WHAT_IS = "what_is"            # a term the reader may not know
    WHY = "why"                    # why the claim holds
    HOW_KNOWN = "how_known"        # what evidence establishes it
    SO_WHAT = "so_what"            # what it changes downstream
    HOW_MEASURED = "how_measured"  # the method and its assumptions
    WHAT_IF_WRONG = "what_if_wrong"
    OBJECTION = "objection"        # the reasonable disagreement, answered
    ALTERNATIVE = "alternative"    # what else could explain this

    @property
    def order(self) -> int:
        """Reading order within a level. Definitions first — you cannot evaluate a claim
        whose words you do not have. Objections last, because they presume the claim."""
        return {
            "what_is": 0, "why": 1, "how_known": 2, "how_measured": 3,
            "so_what": 4, "what_if_wrong": 5, "alternative": 6, "objection": 7,
        }[self.value]


class FollowUp(BaseModel):
    """One anticipated question, its answer, and the questions that answer provokes.

    Recursive by design. ``children`` are the questions a reader would ask *after reading
    this answer*, which is a different set from the questions they would ask before.
    """

    question: str = Field(..., min_length=8)
    answer: str = Field(..., min_length=15)
    kind: FollowUpKind = FollowUpKind.WHY
    children: list[FollowUp] = Field(default_factory=list)
    defines: list[str] = Field(
        default_factory=list,
        description=(
            "Terms this answer defines well enough that descendants may use them freely. "
            "How a `what_is` child discharges its parent's jargon debt."
        ),
    )
    evidence: list[Evidence] = Field(default_factory=list)
    audience_hint: str | None = Field(
        default=None,
        description="Who most needs this branch, e.g. 'no background' or 'medicinal chemist'.",
    )

    @field_validator("question")
    @classmethod
    def _is_a_question(cls, v: str) -> str:
        v = v.strip()
        if not v.endswith("?"):
            raise ValueError(
                f"follow-up question must be phrased as a question and end with '?': {v!r}. "
                "A heading invites skimming; a question invites an answer, and the reader "
                "clicks because they recognise their own question in it."
            )
        return v

    @model_validator(mode="after")
    def _answer_is_not_the_question(self) -> FollowUp:
        q = self.question.strip().lower().rstrip("?")
        a = self.answer.strip().lower().rstrip(".")
        if a == q or a.startswith(q):
            raise ValueError(f"answer restates the question: {self.question!r}")
        # A child that asks its parent's question again makes a loop the reader can fall
        # into: click deeper, read the same thing, click deeper.
        for kid in self.children:
            if kid.question.strip().lower() == self.question.strip().lower():
                raise ValueError(
                    f"child repeats its parent's question ({self.question!r}), so opening "
                    "it returns the reader to where they already are"
                )
        return self

    # -- traversal ---------------------------------------------------------

    def depth(self) -> int:
        """Levels in this subtree, counting itself as 1."""
        return 1 + max((k.depth() for k in self.children), default=0)

    def walk(self, level: int = 1) -> list[tuple[int, FollowUp]]:
        out = [(level, self)]
        for kid in self.children:
            out += kid.walk(level + 1)
        return out

    def count(self) -> int:
        return 1 + sum(k.count() for k in self.children)

    def defined_here_and_below(self) -> set[str]:
        """Terms this node and its descendants define."""
        out = {d.lower().strip() for d in self.defines}
        for kid in self.children:
            out |= kid.defined_here_and_below()
        return out

    def sorted_children(self) -> list[FollowUp]:
        """Children in reading order: definitions before claims, objections last."""
        return sorted(self.children, key=lambda k: (k.kind.order, k.question.lower()))

    # -- the completeness rule --------------------------------------------

    def unexplained_terms(self, inherited: set[str]) -> list[tuple[str, list[str]]]:
        """Jargon used but neither glossed nor explained by a child, with the path to it.

        ``inherited`` is everything defined above this point — the glossary plus every
        ancestor's ``defines``. A term counts as explained if a *child* defines it, because
        the reader can click through; it does not count if only a sibling or a cousin does,
        since nothing leads the reader there.
        """
        available = inherited | {d.lower().strip() for d in self.defines}
        available |= {d.lower().strip() for kid in self.children for d in kid.defines}

        out: list[tuple[str, list[str]]] = []
        if terms := undefined_jargon(self.answer, available):
            out.append((self.question, terms))
        for kid in self.children:
            out += kid.unexplained_terms(available)
        return out

    def problems(self, glossary_terms: set[str], level: int = 1) -> list[str]:
        """Ways this branch fails the reader. Advisory checks live here, hard ones above."""
        out: list[str] = []
        available = glossary_terms | {d.lower().strip() for d in self.defines}
        available |= {d.lower().strip() for kid in self.children for d in kid.defines}

        if level > MAX_DEPTH:
            out.append(
                f"depth {level} exceeds the {MAX_DEPTH}-level contract at {self.question!r}"
            )

        words = len(self.answer.split())
        budget = WORD_BUDGET.get(level, WORD_BUDGET[MAX_DEPTH])
        if words > budget * 1.5:
            out.append(
                f"L{level} answer to {self.question[:48]!r} runs {words} words against a "
                f"{budget}-word budget. Depth is the mechanism for detail here — push the "
                "elaboration into a child rather than making the reader read past it."
            )
        if (msl := mean_sentence_length(self.answer)) > 32:
            out.append(
                f"L{level} answer to {self.question[:48]!r} averages {msl:.0f} words per "
                "sentence, which is where a reader who needed this disclosure loses the thread"
            )
        if terms := undefined_jargon(self.answer, available):
            out.append(
                f"L{level} answer to {self.question[:48]!r} uses {terms} with nothing to "
                "click: not in the glossary, not defined here, and no child explains it. "
                "This is the failure the nesting exists to prevent — the reader hits a "
                "word they do not have and the trail ends."
                + (
                    f" At depth {MAX_DEPTH} there is no room for a child, so these must be "
                    "glossed or rewritten."
                    if level >= MAX_DEPTH else ""
                )
            )
        for kid in self.sorted_children():
            out += kid.problems(available, level + 1)
        return out


class FollowUpTree(BaseModel):
    """The disclosure tree attached to one finding or report section.

    Ordered so the shallowest, most-likely question sits first. The reader who stops after
    the top level should still have got the point; that is what ``lede`` is for.
    """

    lede: str = Field(
        ..., min_length=20,
        description=(
            "The one thing a reader gets if they open nothing. Must stand alone — it is "
            "what most readers will actually read."
        ),
    )
    branches: list[FollowUp] = Field(default_factory=list)

    def depth(self) -> int:
        return max((b.depth() for b in self.branches), default=0)

    def count(self) -> int:
        return sum(b.count() for b in self.branches)

    def sorted_branches(self) -> list[FollowUp]:
        return sorted(self.branches, key=lambda b: (b.kind.order, b.question.lower()))

    def defined_terms(self) -> set[str]:
        out: set[str] = set()
        for b in self.branches:
            out |= b.defined_here_and_below()
        return out

    def depth_profile(self) -> dict[int, int]:
        """Nodes per level. A tree that is all breadth and no depth has not anticipated
        the second question, only the first."""
        prof: dict[int, int] = {}
        for b in self.branches:
            for level, _ in b.walk():
                prof[level] = prof.get(level, 0) + 1
        return dict(sorted(prof.items()))

    def dead_ends(self, glossary_terms: set[str]) -> list[tuple[str, list[str]]]:
        """Every place the reader's trail runs out, with the question it ran out under."""
        out: list[tuple[str, list[str]]] = []
        for b in self.branches:
            out += b.unexplained_terms(glossary_terms)
        return out

    def problems(self, glossary_terms: set[str]) -> list[str]:
        out: list[str] = []
        if not self.branches:
            out.append(
                "no follow-ups: the reader has a claim and nowhere to go with it. At "
                "minimum anticipate the definition question and the so-what question."
            )
            return out

        if (msl := mean_sentence_length(self.lede)) > 32:
            out.append(f"lede averages {msl:.0f} words per sentence — it will not be skimmed")
        if terms := undefined_jargon(self.lede, glossary_terms | self.defined_terms()):
            out.append(
                f"lede uses undefined jargon {terms}. The lede is the part everyone reads, "
                "so it is the one place jargon costs the most."
            )

        kinds = {b.kind for b in self.branches}
        if FollowUpKind.WHAT_IS not in kinds and FollowUpKind.WHY not in kinds:
            out.append(
                "no `what_is` or `why` branch. Those are the two questions a reader "
                "actually has first; starting at `so_what` assumes they accepted the claim."
            )
        if FollowUpKind.SO_WHAT not in kinds:
            out.append(
                "no `so_what` branch — the tree explains the claim without saying what it "
                "changes, which is knowledge-telling rather than knowledge-building"
            )
        if self.depth() < 2:
            out.append(
                "tree is one level deep, so it anticipates the reader's first question and "
                "none of the questions its own answers provoke"
            )
        prof = self.depth_profile()
        if prof.get(1, 0) > 7:
            out.append(
                f"{prof[1]} top-level questions. Past about seven the reader scans a menu "
                "instead of recognising their question; group them under fewer parents."
            )
        for b in self.sorted_branches():
            out += b.problems(glossary_terms | self.defined_terms(), level=1)
        return out

    def summary(self) -> str:
        prof = " ".join(f"L{k}:{v}" for k, v in self.depth_profile().items())
        lines = [
            f"Follow-up tree: {self.count()} questions, depth {self.depth()}  [{prof}]",
            f"  lede: {self.lede[:88]}",
        ]
        for b in self.sorted_branches():
            for level, node in b.walk():
                lines.append(f"  {'  ' * level}{'└ ' if level > 1 else ''}{node.question}")
        return "\n".join(lines)
