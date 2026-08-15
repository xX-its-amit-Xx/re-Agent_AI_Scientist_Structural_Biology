"""DataRef — a pointer to a dataset, resolved lazily.

The division of labour this encodes:

* **Stage 1 records where data lives.** It writes a ``Dataset`` node carrying a
  ``DataRef``: the URL, the format, the size, the licence, what it measures, and
  how to fetch it. It does **not** download anything.
* **Stage 2 (or any later stage) materialises what it needs.** When the biochem
  agent decides it must actually read an assay table to map functional groups onto
  pocket residues, it resolves the ``DataRef``, fetches, checksums, and caches.

Why lazy is the right call and not just laziness:

1. A broad Stage-1 sweep finds hundreds of candidate datasets across ChEMBL,
   BindingDB, Zenodo, HuggingFace, GitHub, and old competition pages. Downloading
   them all would cost tens of gigabytes to answer questions about three of them.
2. The *metadata* is what supports graph reasoning. "Is there a binding assay
   between this compound class and this receptor?" is answerable from metadata
   alone, and that is the question Stage 1 exists to answer.
3. Fetch is the step that fails — dead links, moved repos, licence gates,
   registration walls. Separating discovery from fetch means a broken link degrades
   one node instead of aborting the harvest, and the graph records the breakage.
4. Provenance improves. ``retrieved_utc`` plus ``sha256`` on the materialised copy
   pins exactly what was analysed, which a URL alone never does.

The local cache lives under ``data/cache/<dataset-id>/`` and is gitignored; the
graph is the index, the cache is disposable.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Access(str, Enum):
    OPEN = "open"                    # direct download, no gate
    REGISTRATION = "registration"    # free account needed (Kaggle, some portals)
    API_KEY = "api_key"              # programmatic key required
    REQUEST = "request"              # must email/apply
    RESTRICTED = "restricted"        # licence forbids our use — record and move on
    UNKNOWN = "unknown"


class DataFormat(str, Enum):
    CSV = "csv"
    TSV = "tsv"
    PARQUET = "parquet"
    JSON = "json"
    SDF = "sdf"                      # chemical structures
    SMILES = "smiles"
    PDB = "pdb"
    MMCIF = "mmcif"
    FASTA = "fasta"
    HDF5 = "hdf5"
    ARCHIVE = "archive"              # zip/tar containing several of the above
    NOTEBOOK = "notebook"
    OTHER = "other"


class MeasurementKind(str, Enum):
    """What a dataset actually measures. Drives whether it can answer a question."""

    BINDING_AFFINITY = "binding_affinity"       # Kd, Ki, IC50, EC50
    ACTIVITY = "activity"                       # functional / cell-based readout
    INDUCTION = "induction"                     # transcriptional response
    THERMAL_SHIFT = "thermal_shift"
    STRUCTURE = "structure"                     # coordinates
    ENRICHMENT = "enrichment"                   # DEL selection counts
    PROPERTY = "property"                       # physicochemical / ADME
    KINETICS = "kinetics"
    SELECTIVITY_PANEL = "selectivity_panel"
    PREDICTION = "prediction"                   # someone else's model output
    OTHER = "other"


class DataRef(BaseModel):
    """Everything needed to decide whether to fetch, and how, without fetching."""

    # -- identity ---------------------------------------------------------
    id: str = Field(
        ...,
        description=(
            "Namespaced dataset id, e.g. 'zenodo:10.5281/zenodo.1234567', "
            "'hf:dargason/cofold', 'github:owner/repo#path/to/file.csv', "
            "'kaggle:competition-slug', 'chembl:CHEMBL240/activities'."
        ),
    )
    title: str
    url: str = Field(..., description="Resolvable landing page or direct download URL.")
    download_url: str | None = Field(
        default=None, description="Direct file URL when it differs from the landing page."
    )

    # -- what is in it ----------------------------------------------------
    measures: list[MeasurementKind] = Field(
        default_factory=list, description="What it measures. Empty means we could not tell."
    )
    fmt: DataFormat = DataFormat.OTHER
    n_records: int | None = Field(default=None, description="Rows/entries, if stated.")
    size_bytes: int | None = Field(default=None, description="Download size, if stated.")
    entities: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Graph node ids this dataset covers, keyed by role: "
            "{'targets': ['uniprot:O75469'], 'compounds': ['chembl:...'], "
            "'assays': ['assay:...']}. This is what makes the dataset findable by a "
            "downstream agent asking 'what data exists for this pair?'."
        ),
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Column/field names if discoverable without downloading. Cheap and useful.",
    )

    # -- can we use it ----------------------------------------------------
    access: Access = Access.UNKNOWN
    licence: str | None = Field(default=None, description="e.g. 'CC BY 4.0', 'CC0', 'unknown'.")
    fetch_hint: str | None = Field(
        default=None,
        description=(
            "How to actually get it, when it is not a plain GET — the API call, the "
            "CLI command, the env var holding the key. Write this at discovery time; "
            "rediscovering it later is pure waste."
        ),
    )

    # -- provenance -------------------------------------------------------
    discovered_by: str = Field(..., description="Skill that found it.")
    source_locator: str | None = Field(
        default=None, description="Where we learned of it, e.g. the paper that cites it."
    )

    # -- materialisation state (written by the fetch step, not by discovery)
    local_path: str | None = Field(
        default=None, description="Repo-relative cache path once fetched. None = not fetched."
    )
    sha256: str | None = None
    retrieved_utc: datetime | None = None
    fetch_error: str | None = Field(
        default=None,
        description=(
            "Why fetch failed. A dead link is a finding worth keeping — it stops the "
            "next agent repeating the attempt."
        ),
    )
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def _namespaced(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(f"dataset id {v!r} must be namespaced '<source>:<accession>'")
        return v

    @model_validator(mode="after")
    def _usable_or_explained(self) -> DataRef:
        if self.access in {Access.API_KEY, Access.REGISTRATION, Access.REQUEST} and not self.fetch_hint:
            raise ValueError(
                f"dataset {self.id} needs {self.access.value} access but has no fetch_hint — "
                "record how to get in while you know, or the next agent has to rediscover it"
            )
        if self.local_path and not self.retrieved_utc:
            raise ValueError(
                f"dataset {self.id} claims a local_path but no retrieved_utc; a cached file "
                "with no retrieval timestamp cannot be trusted as provenance"
            )
        return self

    # -- convenience ------------------------------------------------------

    @property
    def is_materialised(self) -> bool:
        return bool(self.local_path) and not self.fetch_error

    @property
    def is_fetchable(self) -> bool:
        """Whether a later stage can realistically get this without human action."""
        return self.access in {Access.OPEN, Access.API_KEY}

    def covers(self, node_id: str) -> bool:
        return any(node_id in ids for ids in self.entities.values())

    def answers(self, kind: MeasurementKind) -> bool:
        return kind in self.measures

    def to_node_attrs(self) -> dict[str, Any]:
        """Flatten for storage on a ``Dataset`` graph node's ``attrs``."""
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_node_attrs(cls, attrs: dict[str, Any]) -> DataRef:
        return cls.model_validate(attrs)


class FetchPlan(BaseModel):
    """What a later stage intends to download, costed before it commits.

    Stage 2 builds one of these from a graph query, and it is reviewable: a human
    can see 40 GB queued and object before anything moves.
    """

    run_id: str
    requested_by: str
    purpose: str = Field(
        ..., min_length=15, description="The question the data will answer. No purpose, no fetch."
    )
    datasets: list[DataRef] = Field(default_factory=list)
    max_total_bytes: int | None = Field(
        default=None, description="Refuse to exceed this. Guards against a runaway sweep."
    )

    def total_bytes(self) -> int:
        return sum(d.size_bytes or 0 for d in self.datasets)

    def unknown_size_count(self) -> int:
        return sum(1 for d in self.datasets if d.size_bytes is None)

    def blocked(self) -> list[DataRef]:
        """Datasets that need a human — surface these instead of silently skipping."""
        return [d for d in self.datasets if not d.is_fetchable]

    def within_budget(self) -> bool:
        return self.max_total_bytes is None or self.total_bytes() <= self.max_total_bytes

    def summary(self) -> str:
        gb = self.total_bytes() / 1e9
        lines = [
            f"Fetch plan for {self.run_id} ({self.requested_by})",
            f"  purpose: {self.purpose}",
            f"  {len(self.datasets)} datasets, {gb:.2f} GB known"
            + (f", {self.unknown_size_count()} of unknown size" if self.unknown_size_count() else ""),
        ]
        if blocked := self.blocked():
            lines.append(f"  {len(blocked)} need human action:")
            lines += [f"    - {d.id} ({d.access.value}): {d.fetch_hint or 'no hint recorded'}"
                      for d in blocked]
        if not self.within_budget():
            lines.append(
                f"  OVER BUDGET: {gb:.2f} GB exceeds the {self.max_total_bytes / 1e9:.2f} GB cap"
            )
        return "\n".join(lines)
