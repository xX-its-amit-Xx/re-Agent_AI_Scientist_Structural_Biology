"""Structure fetching, parsing, and comparison.

Deliberately small: enough to fetch two structures by graph node id, superpose them,
and say what is similar. Read ``align.py``'s module docstring before quoting any
number it returns — the similarity metrics are sequence-guided estimates, not the
output of a structural aligner, and they are labelled as such.
"""

from .align import Alignment, ResiduePair, kabsch, needleman_wunsch, pocket_comparison, superpose
from .model import Ligand, Residue, Structure, fetch, parse_pdb

__all__ = [
    "Alignment",
    "Ligand",
    "Residue",
    "ResiduePair",
    "Structure",
    "fetch",
    "kabsch",
    "needleman_wunsch",
    "parse_pdb",
    "pocket_comparison",
    "superpose",
]
