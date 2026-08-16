"""Follow-up trees for the demo report.

Written by hand rather than generated, because the point of the fixture is to exercise the
checks a real tree has to pass — the completeness rule especially. Every unexplained term in
an answer here is either in the run glossary or is the subject of a child, and
``dead_ends()`` returns empty as a result. If it stops doing so, the fixture has drifted from
the contract and one of them is wrong.

The trees are deliberately about the *fixture's* real content, including the fact that its
numbers are placeholders. A tree that interpreted an illustrative number as measured would be
the exact failure the report is supposed to make impossible.
"""

from __future__ import annotations

from reagent.contracts.followup import FollowUp, FollowUpKind, FollowUpTree


def _q(question: str, answer: str, kind: FollowUpKind, **kw) -> FollowUp:
    return FollowUp(question=question, answer=answer, kind=kind, **kw)


def report_tree() -> FollowUpTree:
    """Questions about the run as a whole rather than about any one finding."""
    return FollowUpTree(
        lede=(
            "This run maps out which other proteins resemble the target, in several "
            "different senses of resemble, and records what each kind of resemblance "
            "would let a later stage borrow. The numbers in it are placeholders: the "
            "structure of the answer is real, the values are not yet."
        ),
        branches=[
            _q(
                "Why are the numbers placeholders?",
                "Because this run exists to check that the pipeline's plumbing is right "
                "before any expensive tool is pointed at it. Every scored link is flagged "
                "as illustrative, and the contract refuses to let one be used as an "
                "assumption downstream.",
                FollowUpKind.HOW_KNOWN,
                children=[
                    _q(
                        "How does the contract actually stop someone using them?",
                        "A link marked illustrative cannot be cited above the lowest "
                        "confidence level, and anything reading the graph has to check "
                        "that flag before treating a value as measured. It is a rule the "
                        "code enforces, not a note in a document.",
                        FollowUpKind.WHY,
                    ),
                ],
            ),
            _q(
                "Why look for several kinds of resemblance instead of one?",
                "Because proteins can be alike in ways that do not travel together. Two "
                "can have almost the same shape and behave differently, or have quite "
                "different shapes and share the exact problem we care about. Collapsing "
                "that into a single similarity score throws away which kind you had.",
                FollowUpKind.WHY,
                children=[
                    _q(
                        "What is an example of the second case?",
                        "Proteins whose job is to detect unfamiliar chemicals all need a "
                        "pocket that can change shape to fit whatever turns up. Two such "
                        "proteins share that difficulty even if they are unrelated, and "
                        "solving it for one tells you something about the other.",
                        FollowUpKind.WHY,
                        defines=["adaptable pocket"],
                    ),
                ],
            ),
            _q(
                "What does this change for whoever works on this next?",
                "They get a ranked shortlist of reference proteins. Each one comes with "
                "the reason it is on the list. So they can choose references for a stated "
                "reason instead of defaulting to the closest relative.",
                FollowUpKind.SO_WHAT,
                children=[
                    _q(
                        "Why is defaulting to the closest relative a problem?",
                        "It is often right and it is never examined. When the thing that "
                        "makes the target hard is shared by something unrelated, the "
                        "closest relative is the wrong choice and nobody notices, because "
                        "no alternative was written down.",
                        FollowUpKind.WHY,
                    ),
                ],
            ),
        ],
    )


def follow_ups() -> dict[str, FollowUpTree]:
    """One tree per decision-bearing finding, keyed by finding id."""
    return {
        "F-CONSTRAINT-01": FollowUpTree(
            lede=(
                "Every number in this run is a stand-in. The shapes of the relationships "
                "are real and the values are invented, so nothing here should be used to "
                "make a decision about a real molecule."
            ),
            branches=[
                _q(
                    "Then what is this run for?",
                    "To prove the machinery works end to end: that the search runs, the "
                    "results land in the right structure, the checks catch mistakes, and "
                    "the report comes out readable. Those are exactly the things that are "
                    "expensive to fix after real results exist.",
                    FollowUpKind.WHY,
                    children=[
                        _q(
                            "Why not just run the real tools first?",
                            "Because some of them cost money or need a cluster, and a "
                            "plumbing mistake found afterwards means paying twice. A run "
                            "with invented values costs nothing and finds the same "
                            "structural mistakes.",
                            FollowUpKind.WHY,
                        ),
                    ],
                ),
                _q(
                    "What happens if someone uses one of these numbers anyway?",
                    "The checks refuse it. A value flagged as a stand-in cannot be quoted "
                    "with any real confidence, and a later stage that tries to build on "
                    "one fails its own validation rather than quietly producing a "
                    "confident wrong answer.",
                    FollowUpKind.SO_WHAT,
                    children=[
                        _q(
                            "Could a stand-in slip through unflagged?",
                            "Yes, if whoever wrote it forgot the flag. That is why the flag "
                            "is counted rather than trusted: the run reports how many "
                            "scored links carry it, and a number that disagrees with the "
                            "total is the signal to go looking.",
                            FollowUpKind.WHAT_IF_WRONG,
                        ),
                    ],
                ),
            ],
        ),
        "F-PROMISC-01": FollowUpTree(
            lede=(
                "The proteins that bind the widest range of molecules are mostly not "
                "close relatives of the target. They are worth borrowing from anyway, "
                "because what they share with the target is a difficulty rather than a "
                "shape."
            ),
            branches=[
                _q(
                    "What does it mean for a protein to bind a wide range of molecules?",
                    "Most proteins are fussy: one specific molecule fits and almost "
                    "nothing else does. A few are the opposite, and will hold hundreds of "
                    "unrelated molecules. That breadth is usually their job, not a defect.",
                    FollowUpKind.WHAT_IS,
                    defines=["promiscuity", "promiscuous"],
                    children=[
                        _q(
                            "Why would a protein be built to be unfussy?",
                            "Because its job is to notice chemicals the body has never "
                            "encountered. Anything shaped for one specific molecule would "
                            "miss all the others, so being unfussy is the whole point.",
                            FollowUpKind.WHY,
                        ),
                        _q(
                            "How would we know it is genuinely unfussy rather than just "
                            "well studied?",
                            "By comparing how many different molecules it holds against "
                            "how many have been tried on it. A protein tested against ten "
                            "thousand compounds will look broader than one tested against "
                            "fifty, and that difference is about the testing.",
                            FollowUpKind.HOW_MEASURED,
                        ),
                    ],
                ),
                _q(
                    "Why does sharing a difficulty help more than sharing a shape?",
                    "Because the difficulty is what makes the prediction hard. Two "
                    "unfussy proteins both defeat the same shortcut — using one fixed "
                    "snapshot of the protein — so whatever was needed to handle one is "
                    "likely to be needed for the other.",
                    FollowUpKind.WHY,
                    children=[
                        _q(
                            "What is the shortcut, and why does it fail here?",
                            "The shortcut is to treat the protein as a fixed shape and ask "
                            "what fits. It fails when the shape changes depending on what "
                            "is being held, because then there is no single correct shape "
                            "to test against.",
                            FollowUpKind.WHY,
                            children=[
                                _q(
                                    "So which shape do people usually pick?",
                                    "Whichever one was measured most clearly. That choice "
                                    "has nothing to do with which shape is most common, so "
                                    "it quietly decides the answer on the basis of who ran "
                                    "the cleanest experiment.",
                                    FollowUpKind.HOW_MEASURED,
                                ),
                            ],
                        ),
                    ],
                ),
                _q(
                    "What does this change downstream?",
                    "It argues for drawing reference structures from unfussy proteins "
                    "outside the target's family, not only from its close relatives — and "
                    "for expecting the worst errors on the largest molecules.",
                    FollowUpKind.SO_WHAT,
                    children=[
                        _q(
                            "What if the reasoning is wrong?",
                            "Then references from unrelated proteins add noise instead of "
                            "coverage, and predictions get worse for the small molecules a "
                            "single close relative would have handled well. The check is "
                            "whether the borrowed references actually span shapes the "
                            "close relatives do not.",
                            FollowUpKind.WHAT_IF_WRONG,
                        ),
                    ],
                ),
            ],
        ),
        "F-NEG-01": FollowUpTree(
            lede=(
                "Five of the seven planned comparisons were never made. That is not a "
                "result about the target; it is a gap in the work, and it is recorded here "
                "so nobody mistakes the quiet axes for empty ones."
            ),
            branches=[
                _q(
                    "What is the difference between a comparison that found nothing and "
                    "one that was never made?",
                    "A comparison that found nothing tells you something: the "
                    "relationship is not there. One that was never made tells you "
                    "nothing at all. From the outside they look identical, which is why "
                    "the distinction has to be written down rather than inferred.",
                    FollowUpKind.WHY,
                    children=[
                        _q(
                            "Why can't we tell them apart later?",
                            "Because absence leaves no trace. A report lists what was "
                            "found, so a missing relationship is invisible — there is no "
                            "empty row to notice. The only record is the one made at the "
                            "time.",
                            FollowUpKind.WHY,
                        ),
                    ],
                ),
                _q(
                    "What should the next stage do about it?",
                    "Treat the unmade comparisons as open, not as negative. Anything "
                    "built on the assumption that those relationships are absent is "
                    "resting on work that was never done.",
                    FollowUpKind.SO_WHAT,
                ),
            ],
        ),
        "F-DESIGN-01": FollowUpTree(
            lede=(
                "Each kind of similarity gets its own labelled relationship in the graph "
                "instead of everything sharing one generic 'is similar to'. That makes "
                "later questions answerable that would otherwise be guesswork."
            ),
            branches=[
                _q(
                    "What would go wrong with one generic similarity link?",
                    "You could no longer ask for one kind of similarity while excluding "
                    "another. Every question would return everything, and the reason two "
                    "things were linked would be lost the moment it was recorded.",
                    FollowUpKind.WHY,
                    children=[
                        _q(
                            "What is an example of a question that needs the distinction?",
                            "Find proteins that share the target's binding-site "
                            "difficulty but are not its close relatives. With labelled "
                            "links that is a single lookup. With one generic link it is "
                            "unanswerable, because the label carrying 'why' was discarded.",
                            FollowUpKind.SO_WHAT,
                        ),
                    ],
                ),
                _q(
                    "What does this let a later stage actually do?",
                    "Ask for one kind of relationship while ruling out another — for "
                    "instance, proteins that share the target's binding-site difficulty "
                    "but are not its close relatives. That is the shortlist the next stage "
                    "needs, and it is one lookup rather than a judgement call.",
                    FollowUpKind.SO_WHAT,
                ),
                _q(
                    "What does this cost?",
                    "A longer vocabulary to learn and to keep consistent, and a rule that "
                    "every new kind of link has to declare which types of thing it is "
                    "allowed to connect. That check is what stops the vocabulary drifting "
                    "into a second generic link under a different name.",
                    FollowUpKind.WHAT_IF_WRONG,
                ),
            ],
        ),
    }
