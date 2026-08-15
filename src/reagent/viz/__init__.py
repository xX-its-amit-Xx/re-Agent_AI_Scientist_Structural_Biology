"""Renderers. Every figure this package produces is self-contained.

The publish target blocks all external hosts, so nothing here may reference a CDN,
a remote font, or a runtime fetch. Third-party JavaScript is vendored under
``assets/vendor/`` and inlined at render time.
"""

from .charts import heatmap, histogram, provenance_chain, ranked_bar, scatter
from .graph_html import extract_ego, render
from .obsidian import export as export_obsidian

__all__ = [
    "export_obsidian",
    "extract_ego",
    "heatmap",
    "histogram",
    "provenance_chain",
    "ranked_bar",
    "render",
    "scatter",
]
