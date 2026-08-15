"""Knowledge-graph storage and querying.

JSONL is the source of truth; SQLite is a rebuildable cache. See
``reagent.kg.store`` for the rationale.
"""

from .store import KGStore, default_store

__all__ = ["KGStore", "default_store"]
