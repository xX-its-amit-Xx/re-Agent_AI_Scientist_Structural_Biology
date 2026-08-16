"""Knowledge-graph store: JSONL source of truth, SQLite query layer.

Why this shape:

* **JSONL is the truth.** Append-only, git-diffable, one assertion per line
  with its provenance attached. Two agents can write concurrently without a
  lock and a human can review the diff.
* **SQLite is a cache.** Rebuilt from the JSONL whenever it is stale. Nothing
  is ever stored only in the database, so deleting ``kg.sqlite`` is always safe.
  stdlib only — no server, no driver to install on a hackathon laptop.

The point of the SQL layer is that a downstream agent asks a *question*, not a
graph-traversal puzzle:

    store.neighbors("uniprot:O75469", Predicate.SIMILAR_FOLD_TO, min_confidence=...)
    store.query(SQL)  # escape hatch, read-only

``ATTRS`` values are stored twice: as raw JSON in ``attrs_json`` and flattened
into an ``edge_attrs`` table so numeric filters (``tm_score > 0.7``) work in SQL
without JSON functions.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from reagent.contracts import (
    AxisSpec,
    Confidence,
    Edge,
    GraphDelta,
    Node,
    Predicate,
    read_jsonl,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    label       TEXT NOT NULL,
    aliases     TEXT,
    attrs_json  TEXT,
    asserted_by TEXT,
    run_id      TEXT,
    created_utc TEXT
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);

CREATE TABLE IF NOT EXISTS edges (
    rowid_      INTEGER PRIMARY KEY AUTOINCREMENT,
    src         TEXT NOT NULL,
    predicate   TEXT NOT NULL,
    dst         TEXT NOT NULL,
    confidence  TEXT,
    conf_rank   INTEGER,
    attrs_json  TEXT,
    commentary  TEXT,
    n_evidence  INTEGER DEFAULT 0,
    evidence_json TEXT,
    asserted_by TEXT,
    run_id      TEXT,
    created_utc TEXT,
    UNIQUE(src, predicate, dst)
);
CREATE INDEX IF NOT EXISTS idx_edges_src  ON edges(src, predicate);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON edges(dst, predicate);
CREATE INDEX IF NOT EXISTS idx_edges_pred ON edges(predicate);

-- Flattened numeric/text attributes so plain SQL can filter on them.
CREATE TABLE IF NOT EXISTS edge_attrs (
    src       TEXT NOT NULL,
    predicate TEXT NOT NULL,
    dst       TEXT NOT NULL,
    key       TEXT NOT NULL,
    num       REAL,
    txt       TEXT
);
CREATE INDEX IF NOT EXISTS idx_eattr ON edge_attrs(key, num);
CREATE INDEX IF NOT EXISTS idx_eattr_edge ON edge_attrs(src, predicate, dst);

-- Convenience view: every edge with both endpoint labels and types resolved.
CREATE VIEW IF NOT EXISTS edges_labeled AS
SELECT e.src, ns.type AS src_type, ns.label AS src_label,
       e.predicate,
       e.dst, nd.type AS dst_type, nd.label AS dst_label,
       e.confidence, e.conf_rank, e.attrs_json, e.n_evidence, e.asserted_by
FROM edges e
LEFT JOIN nodes ns ON ns.id = e.src
LEFT JOIN nodes nd ON nd.id = e.dst;
"""

_CONF_RANK = {c.value: c.rank for c in Confidence}


class KGStore:
    """Read/write access to one knowledge graph directory."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.nodes_path = self.root / "nodes.jsonl"
        self.edges_path = self.root / "edges.jsonl"
        self.db_path = self.root / "kg.sqlite"

    # -- writing --------------------------------------------------------

    def merge(self, delta: GraphDelta, *, strict: bool = True) -> list[str]:
        """Validate against the full graph, then append. Returns the problem list.

        With ``strict=True`` (the default) a delta with any referential problem is
        rejected wholesale rather than partially written — a half-merged delta is
        much worse to debug than a rejected one.

        This is the sanctioned write path because it is the only one that knows the
        *stored* nodes and their types, so an edge attaching to a pre-existing node
        gets endpoint type-checking too.
        """
        problems = delta.validate_referential_integrity(
            known_ids=self.node_ids(), known_types=self.node_types()
        )
        if problems and strict:
            return problems
        # Already validated above with full graph knowledge; re-validating inside
        # write_jsonl would fail on endpoints that exist only in the stored graph.
        delta.write_jsonl(self.root, validate=False)
        self._invalidate()
        return problems

    def _invalidate(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    # -- reading --------------------------------------------------------

    def node_ids(self) -> set[str]:
        """Cheap existence check without building the database."""
        if not self.nodes_path.exists():
            return set()
        out: set[str] = set()
        with self.nodes_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.add(json.loads(line)["id"])
        return out

    def node_types(self) -> dict[str, str]:
        """Map stored node id -> type name, so a delta's edges can be type-checked
        against endpoints that exist only in the stored graph."""
        if not self.nodes_path.exists():
            return {}
        out: dict[str, str] = {}
        with self.nodes_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    out[rec["id"]] = rec["type"]
        return out

    def iter_nodes(self) -> Iterable[Node]:
        return read_jsonl(self.nodes_path, Node)

    def iter_edges(self) -> Iterable[Edge]:
        return read_jsonl(self.edges_path, Edge)

    # -- the sqlite cache -----------------------------------------------

    def _is_stale(self) -> bool:
        if not self.db_path.exists():
            return True
        db_mtime = self.db_path.stat().st_mtime
        return any(
            p.exists() and p.stat().st_mtime > db_mtime
            for p in (self.nodes_path, self.edges_path)
        )

    def build(self, *, force: bool = False) -> Path:
        """(Re)build the SQLite cache from the JSONL files."""
        if not force and not self._is_stale():
            return self.db_path
        if self.db_path.exists():
            self.db_path.unlink()
        self.root.mkdir(parents=True, exist_ok=True)

        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(SCHEMA)

            for n in self.iter_nodes():
                # Later assertions about the same node win, and we union aliases
                # so two agents naming it differently both stay findable.
                con.execute(
                    """INSERT INTO nodes(id,type,label,aliases,attrs_json,asserted_by,run_id,created_utc)
                       VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                         label=excluded.label,
                         aliases=excluded.aliases,
                         attrs_json=excluded.attrs_json""",
                    (
                        n.id, n.type.value, n.label, json.dumps(n.aliases),
                        json.dumps(n.attrs), n.asserted_by, n.run_id,
                        n.created_utc.isoformat(),
                    ),
                )

            for e in self.iter_edges():
                rank = _CONF_RANK.get(e.confidence.value, 0)
                # Keep the highest-confidence version of a duplicated triple,
                # and merge its attrs so nobody loses a measurement.
                cur = con.execute(
                    "SELECT conf_rank, attrs_json, commentary FROM edges "
                    "WHERE src=? AND predicate=? AND dst=?",
                    (e.src, e.predicate.value, e.dst),
                )
                existing = cur.fetchone()
                attrs = dict(e.attrs)
                commentary = e.commentary
                if existing:
                    prev_rank, prev_attrs, prev_comment = existing
                    merged = json.loads(prev_attrs or "{}")
                    merged.update(attrs)
                    attrs = merged
                    # Never drop an existing reading in favour of nothing. A lower-confidence
                    # re-assertion of the same triple often carries the better sentence.
                    commentary = commentary or prev_comment
                    if prev_rank >= rank:
                        con.execute(
                            "UPDATE edges SET attrs_json=?, commentary=? "
                            "WHERE src=? AND predicate=? AND dst=?",
                            (json.dumps(attrs), commentary, e.src, e.predicate.value, e.dst),
                        )
                        self._write_attrs(con, e, attrs)
                        continue
                con.execute(
                    """INSERT INTO edges(src,predicate,dst,confidence,conf_rank,attrs_json,
                                         commentary,n_evidence,evidence_json,asserted_by,
                                         run_id,created_utc)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(src,predicate,dst) DO UPDATE SET
                         confidence=excluded.confidence,
                         conf_rank=excluded.conf_rank,
                         attrs_json=excluded.attrs_json,
                         commentary=COALESCE(excluded.commentary, edges.commentary),
                         n_evidence=excluded.n_evidence,
                         evidence_json=excluded.evidence_json""",
                    (
                        e.src, e.predicate.value, e.dst, e.confidence.value, rank,
                        json.dumps(attrs), commentary, len(e.evidence),
                        json.dumps([ev.model_dump(mode="json", exclude_none=True) for ev in e.evidence]),
                        e.asserted_by, e.run_id, e.created_utc.isoformat(),
                    ),
                )
                self._write_attrs(con, e, attrs)

            con.commit()
        finally:
            con.close()
        return self.db_path

    @staticmethod
    def _write_attrs(con: sqlite3.Connection, e: Edge, attrs: dict[str, Any]) -> None:
        con.execute(
            "DELETE FROM edge_attrs WHERE src=? AND predicate=? AND dst=?",
            (e.src, e.predicate.value, e.dst),
        )
        for k, v in attrs.items():
            num = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
            txt = None if num is not None else json.dumps(v) if not isinstance(v, str) else v
            con.execute(
                "INSERT INTO edge_attrs(src,predicate,dst,key,num,txt) VALUES(?,?,?,?,?,?)",
                (e.src, e.predicate.value, e.dst, k, num, txt),
            )

    def connect(self) -> sqlite3.Connection:
        """Read-only-ish connection to a freshly-built cache."""
        self.build()
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """Escape hatch for downstream agents. SELECT-only, by design."""
        stripped = sql.lstrip().lower()
        if not (stripped.startswith("select") or stripped.startswith("with")):
            raise ValueError("KGStore.query accepts SELECT/WITH statements only")
        con = self.connect()
        try:
            return [dict(r) for r in con.execute(sql, params).fetchall()]
        finally:
            con.close()

    # -- canned questions -----------------------------------------------
    # These exist so a downstream skill does not have to know SQL to answer
    # the four Stage-1 axes.

    def neighbors(
        self,
        node_id: str,
        predicate: Predicate | None = None,
        *,
        min_confidence: Confidence = Confidence.SPECULATIVE,
        order_by_attr: str | None = None,
        descending: bool = True,
        limit: int | None = None,
        undirected: bool = False,
    ) -> list[dict[str, Any]]:
        """Adjacent nodes, optionally filtered by predicate/confidence and sorted by an attr."""
        # Every column is table-qualified: the optional edge_attrs join also has
        # src/predicate/dst, so bare names are ambiguous.
        params: list[Any] = []
        join = ""
        if order_by_attr:
            join = (
                " LEFT JOIN edge_attrs a ON a.src=e.src AND a.predicate=e.predicate"
                " AND a.dst=e.dst AND a.key=?"
            )
            params.append(order_by_attr)
            # NULLs last, so edges missing this attribute never outrank scored ones.
            direction = "DESC" if descending else "ASC"
            sort = f" ORDER BY (a.num IS NULL), a.num {direction}"
        else:
            sort = " ORDER BY e.conf_rank DESC, e.n_evidence DESC"

        if undirected:
            where = ["(e.src = ? OR e.dst = ?)"]
            params += [node_id, node_id]
        else:
            where = ["e.src = ?"]
            params.append(node_id)
        if predicate is not None:
            where.append("e.predicate = ?")
            params.append(predicate.value)
        where.append("e.conf_rank >= ?")
        params.append(min_confidence.rank)

        # `other` normalises direction: whichever endpoint is not the queried node.
        # Without it an undirected caller has to re-derive which column is the
        # neighbour, and gets it wrong on reverse-direction edges.
        sql = (
            "SELECT e.src, e.predicate, e.dst, e.confidence, e.attrs_json, e.n_evidence,"
            " e.asserted_by,"
            " nd.label AS dst_label, nd.type AS dst_type,"
            " ns.label AS src_label, ns.type AS src_type,"
            " CASE WHEN e.src = ? THEN e.dst ELSE e.src END AS other,"
            " CASE WHEN e.src = ? THEN nd.label ELSE ns.label END AS other_label,"
            " CASE WHEN e.src = ? THEN nd.type ELSE ns.type END AS other_type,"
            " CASE WHEN e.src = ? THEN 'out' ELSE 'in' END AS direction"
            " FROM edges e"
            " LEFT JOIN nodes nd ON nd.id = e.dst"
            " LEFT JOIN nodes ns ON ns.id = e.src"
            + join
            + " WHERE " + " AND ".join(where)
            + sort
        )
        # The four CASE placeholders come before the JOIN/WHERE ones in the SQL text.
        params = [node_id] * 4 + params
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self.query(sql, params)
        for r in rows:
            r["attrs"] = json.loads(r.pop("attrs_json") or "{}")
        return rows

    def along_axis(
        self,
        node_id: str,
        axis: AxisSpec,
        *,
        min_score: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Neighbours of any node along one declared similarity axis.

        Takes an ``AxisSpec`` rather than a bare predicate so the score key and
        its range travel with the query — the caller cannot accidentally sort a
        TM-score axis by a Tanimoto key.
        """
        rows = self.neighbors(
            node_id,
            Predicate(axis.predicate),
            order_by_attr=axis.score_key,
            limit=None,
            undirected=True,
        )
        if min_score is not None:
            rows = [
                r for r in rows if float(r["attrs"].get(axis.score_key, -1e9)) >= min_score
            ]
        return rows[:limit]

    def neighborhood(
        self,
        node_id: str,
        axes: list[AxisSpec],
        *,
        per_axis_limit: int = 25,
    ) -> dict[str, list[dict[str, Any]]]:
        """The full multi-axis neighbourhood of a target — Stage 1's headline product.

        Returns ``{axis_name: rows}``. This is what Stage 2 and Stage 3 call, and
        what the graph renderer draws as an ego network with one edge colour per
        axis.
        """
        return {a.name: self.along_axis(node_id, a, limit=per_axis_limit) for a in axes}

    def promiscuity_ranking(self, limit: int = 50) -> list[dict[str, Any]]:
        """Proteins ranked by how many distinct compounds they are recorded as binding.

        This is the operational definition of "promiscuous binding partner" that
        Stage 3 uses to pick fine-tuning templates: breadth of BINDS, not a
        literature adjective.
        """
        return self.query(
            """
            SELECT n.id, n.label, COUNT(DISTINCT e.dst) AS n_ligands,
                   MAX(a.num) AS max_reported_breadth
            FROM nodes n
            JOIN edges e ON e.src = n.id AND e.predicate = 'BINDS'
            LEFT JOIN edge_attrs a
                   ON a.src = n.id AND a.predicate = 'PROMISCUOUS_WITH' AND a.key = 'breadth_score'
            WHERE n.type = 'Protein'
            GROUP BY n.id
            ORDER BY n_ligands DESC
            LIMIT ?
            """,
            (limit,),
        )

    def shared_motifs(self, node_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Proteins that share a structural motif with the target, with the motif named."""
        return self.query(
            """
            SELECT other.id, other.label, m.id AS motif_id, m.label AS motif_label,
                   e2.attrs_json AS motif_attrs, e2.confidence
            FROM edges e1
            JOIN nodes m      ON m.id = e1.dst AND m.type = 'Motif'
            JOIN edges e2     ON e2.dst = m.id AND e2.predicate IN ('HAS_MOTIF','SHARES_MOTIF')
            JOIN nodes other  ON other.id = e2.src AND other.id != ?
            WHERE e1.src = ? AND e1.predicate IN ('HAS_MOTIF','SHARES_MOTIF')
            ORDER BY e2.conf_rank DESC
            LIMIT ?
            """,
            (node_id, node_id, limit),
        )

    def family_members(self, family_id: str) -> list[dict[str, Any]]:
        """Everything asserted to be in a family (receptor family, target class, ...)."""
        return self.query(
            """
            SELECT n.id, n.label, n.attrs_json, e.confidence
            FROM edges e JOIN nodes n ON n.id = e.src
            WHERE e.predicate = 'MEMBER_OF_FAMILY' AND e.dst = ?
            ORDER BY n.label
            """,
            (family_id,),
        )

    def evidence_for(self, src: str, predicate: Predicate, dst: str) -> list[dict[str, Any]]:
        """Pull the citations behind one assertion. Stage 2/3 use this to audit Stage 1."""
        rows = self.query(
            "SELECT evidence_json FROM edges WHERE src=? AND predicate=? AND dst=?",
            (src, predicate.value, dst),
        )
        return json.loads(rows[0]["evidence_json"]) if rows else []

    def between(self, a: str, b: str, *, max_hops: int = 2) -> dict[str, Any]:
        """Everything the graph knows about a *pair* of nodes.

        This is what a side-by-side comparison of two nodes has to be built on. A viewer that
        shows two things next to each other and does not say why they are together leaves the
        reader to guess, and the answer is already in the graph — in the edge's predicate, its
        score, its confidence, its citations, and its ``commentary``.

        Returns direct edges in either direction, and when there are none, the two-hop paths
        through a shared neighbour — because "no direct edge" is not the same as "unrelated",
        and the intermediate is usually the interesting part.
        """
        direct = self.query(
            """
            SELECT e.src, e.predicate, e.dst, e.confidence, e.commentary, e.attrs_json,
                   e.n_evidence, e.asserted_by,
                   ns.label AS src_label, ns.type AS src_type,
                   nd.label AS dst_label, nd.type AS dst_type
            FROM edges e
            LEFT JOIN nodes ns ON ns.id = e.src
            LEFT JOIN nodes nd ON nd.id = e.dst
            WHERE (e.src = ? AND e.dst = ?) OR (e.src = ? AND e.dst = ?)
            ORDER BY e.conf_rank DESC, e.predicate
            """,
            (a, b, b, a),
        )
        for r in direct:
            r["attrs"] = json.loads(r.pop("attrs_json") or "{}")
            r["direction"] = "forward" if r["src"] == a else "reverse"

        paths: list[dict[str, Any]] = []
        if not direct and max_hops >= 2:
            # Undirected two-hop, excluding the endpoints themselves as intermediates.
            paths = self.query(
                """
                WITH ends AS (
                  SELECT src AS other, predicate, dst AS anchor, commentary FROM edges
                  UNION ALL
                  SELECT dst AS other, predicate, src AS anchor, commentary FROM edges
                )
                SELECT x.other AS via, n.label AS via_label, n.type AS via_type,
                       x.predicate AS pred_a, y.predicate AS pred_b,
                       x.commentary AS comment_a, y.commentary AS comment_b
                FROM ends x
                JOIN ends y ON y.other = x.other
                LEFT JOIN nodes n ON n.id = x.other
                WHERE x.anchor = ? AND y.anchor = ?
                  AND x.other NOT IN (?, ?)
                ORDER BY x.predicate, y.predicate
                LIMIT 40
                """,
                (a, b, a, b),
            )

        return {
            "a": a, "b": b,
            "direct": direct,
            "paths": paths,
            "commentary": [r["commentary"] for r in direct if r.get("commentary")],
        }

    def uncommented_edges(self, *, scored_only: bool = True) -> list[dict[str, Any]]:
        """Edges carrying a number but no reading of it.

        Advisory. A scored edge with no ``commentary`` is checkable and unusable: it tells a
        reader that two things are related by 0.72 of something and leaves them to work out
        what to do about it. These are the edges a side-by-side view will render as a bare
        number.
        """
        sql = (
            "SELECT src, predicate, dst, confidence, asserted_by FROM edges "
            "WHERE (commentary IS NULL OR TRIM(commentary) = '')"
        )
        if scored_only:
            sql += (
                " AND EXISTS (SELECT 1 FROM edge_attrs a WHERE a.src = edges.src "
                "AND a.predicate = edges.predicate AND a.dst = edges.dst AND a.num IS NOT NULL)"
            )
        return self.query(sql + " ORDER BY predicate, src")

    def unsupported_edges(self, min_confidence: Confidence = Confidence.SUPPORTED) -> list[dict[str, Any]]:
        """Edges claiming confidence they have no citations for. Run this before shipping."""
        return self.query(
            "SELECT src, predicate, dst, confidence, asserted_by FROM edges "
            "WHERE n_evidence = 0 AND conf_rank >= ? ORDER BY predicate",
            (min_confidence.rank,),
        )

    def stats(self) -> dict[str, Any]:
        """Headline numbers for the Model Report's `metrics` block."""
        con = self.connect()
        try:
            by_type = {
                r["type"]: r["n"]
                for r in con.execute("SELECT type, COUNT(*) n FROM nodes GROUP BY type")
            }
            by_pred = {
                r["predicate"]: r["n"]
                for r in con.execute("SELECT predicate, COUNT(*) n FROM edges GROUP BY predicate")
            }
            n_nodes = con.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
            n_edges = con.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
            cited = con.execute("SELECT COUNT(*) c FROM edges WHERE n_evidence > 0").fetchone()["c"]
        finally:
            con.close()
        return {
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "nodes_by_type": by_type,
            "edges_by_predicate": by_pred,
            "cited_edge_fraction": round(cited / n_edges, 3) if n_edges else 0.0,
        }


def default_store(repo_root: Path | str = ".") -> KGStore:
    return KGStore(Path(repo_root) / "kg")
