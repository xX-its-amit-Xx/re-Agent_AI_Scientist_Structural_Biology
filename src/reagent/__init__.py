"""reagent — an AI scientist that designs structural-biology pipelines.

The package is deliberately thin. The intelligence lives in ``skills/`` as
SKILL.md files that an agent reads; this Python layer only provides the things
an agent should never improvise: typed contracts, a knowledge-graph store, a
report renderer, and the decision gate.

Layout
------
    reagent.contracts   ModelReport / GraphDelta / ProposalSet schemas
    reagent.kg          build + query the knowledge graph
    reagent.reports     render a ModelReport to Markdown/HTML
    reagent.skills      read and validate the skill registry
    reagent.cli         the `reagent` command
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
