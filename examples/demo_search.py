"""A search ledger for the demo report.

This is the *exemplary* version: it passes ``--strict``, because the demo report is what a
teammate copies and a reference fixture that fails its own validator teaches the wrong lesson.
Ledgers with the characteristic problems — a redundant channel, an underspent exploration
quota, a coverage estimate resting on two pull channels — live in ``tests/test_discovery.py``
where they belong.

Passing strict does not mean the search was complete, and the difference matters. Estimated
coverage here is about 65% and it is reported as an upper bound; four regions were not searched
at all and are named in ``known_gaps``. **A clean ledger describing an incomplete search is the
normal, honest case** — what strict checks is whether the search is *auditable*, not whether it
is exhaustive.

The numbers are made up, like everything else in the fixture. What is real is their shape: a
keyword channel doing most of the work, a traversal channel contributing the fewest results and
the most unique ones per result, and a coverage figure well under 100%.
"""

from __future__ import annotations

from reagent.contracts.discovery import (
    ChannelYield,
    CoverageEstimate,
    DiscoveryChannel,
    SearchLedger,
)


def demo_ledger(run_id: str) -> SearchLedger:
    return SearchLedger(
        run_id=run_id,
        channels=[
            ChannelYield(
                channel=DiscoveryChannel.KEYWORD_SEARCH,
                n_retrieved=180, n_admitted=34, n_unique=11,
                queries=[
                    "PXR ligand binding domain promiscuity",
                    "nuclear receptor adaptable pocket conformational ensemble",
                    "xenobiotic sensor structure prediction",
                ],
                cost_note="paperclip full-text, 3 query families",
            ),
            ChannelYield(
                channel=DiscoveryChannel.STRUCTURED_QUERY,
                n_retrieved=64, n_admitted=22, n_unique=9,
                queries=["RCSB: uniprot O75469, has ligand, resolution < 3.0"],
            ),
            # Low unique yield relative to volume — the usual result for a second pull
            # channel, since it shares the vocabulary assumption with the first. Kept
            # because 3 unique finds is still 3, and dropped from the coverage pairing
            # for exactly that reason.
            ChannelYield(
                channel=DiscoveryChannel.SEMANTIC_SEARCH,
                n_retrieved=95, n_admitted=18, n_unique=3,
                queries=["proteins that bind structurally unrelated small molecules"],
                cost_note="embedding search; 15 of 18 admitted hits were already found by keyword",
            ),
            # Fewest results, most unique per result. The usual shape, and the reason a
            # search without a traversal channel has an unmeasured blind spot.
            ChannelYield(
                channel=DiscoveryChannel.BACKWARD_SNOWBALL,
                n_retrieved=41, n_admitted=19, n_unique=14,
                queries=["references of PMC8864553 (methods section only)"],
            ),
        ],
        coverage=[
            CoverageEstimate(
                channel_a=DiscoveryChannel.KEYWORD_SEARCH,
                channel_b=DiscoveryChannel.BACKWARD_SNOWBALL,
                n_a=34, n_b=19, n_both=8, n_total_observed=53,
            ),
        ],
        exploration_quota=0.20,
        exploration_spent=0.22,
        saturation_note=(
            "Stopped on the fixture's query budget, not on saturation: the backward-snowball "
            "channel was still returning 14 unique results per 19 admitted when it was cut, "
            "which is a climbing curve rather than a flat one."
        ),
        known_gaps=[
            "No patent search. Paperclip cannot search patents despite its help text, and "
            "no separate patent channel was run — so the densest SAR literature for this "
            "target class is entirely absent.",
            "No non-English channel. Regional indexes were not queried at all.",
            "Negative results were not searched for explicitly, so the corpus is biased "
            "toward methods that reported working.",
            "No graph-gap query was run against the fixture, so connections that exist in "
            "no single paper are unrepresented by construction.",
        ],
    )
