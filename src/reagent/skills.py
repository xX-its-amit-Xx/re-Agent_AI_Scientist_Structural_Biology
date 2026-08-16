"""The skill registry — what the orchestrator routes over.

Two files describe a skill, deliberately:

``SKILL.md``
    Frontmatter (``name``, ``description``, ``allowed-tools``) plus the body. This
    is the portable, harness-standard part; another agent framework can read it
    unchanged, so nothing project-specific goes in here.

``meta.json``
    The pipeline metadata this project adds: which stage, who owns it, whether it
    is implemented, what it consumes and produces, and which credit pools it
    spends. Kept in a separate per-skill file rather than in the frontmatter (so
    it cannot break skill loading) and rather than in one central registry file
    (so three teammates adding skills on three branches do not collide).

``registry.json`` is generated from both and is never hand-edited.

The YAML frontmatter parser here is deliberately minimal — it handles the subset
skills actually use (scalars, folded ``>-`` blocks, and inline lists) so the
package needs no YAML dependency for a teammate who only wants the contracts.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(".claude/skills")
REGISTRY = Path("skills/registry.json")

VALID_STAGES = {
    "stage0_scouting", "stage1_literature", "stage2_biochem",
    "stage3_prior", "stage4_optimization", "synthesis", "shared",
    # "method" is not a pipeline stage and deliberately is not in `contracts.Stage`.
    #
    # It arrived with the Stage 3 execution layer and is a better idea than the taxonomy it
    # broke: a skill like `significance-discipline` or `harness-verification` encodes a
    # domain-general method — bootstrap every comparison, prove the scorer measures what it
    # claims — and binding it to a stage would be a category error. It applies wherever a
    # number gets compared, which is everywhere.
    #
    # Practical consequence: a `method` skill has no place in the stage handoff chain, so the
    # data-flow linter does not expect its `produces` keys to be consumed by a later stage.
    "method",
}
VALID_STATUS = {"implemented", "partial", "stub", "planned"}


# --------------------------------------------------------------------------
# Minimal frontmatter parsing
# --------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a SKILL.md into (frontmatter dict, body).

    Supports what skills use: ``key: value``, folded ``key: >-`` blocks, and
    inline ``[a, b]`` lists. Raises on a missing or unterminated block, because a
    silently-empty frontmatter produces a skill the harness will not load.
    """
    if not text.startswith("---"):
        raise ValueError("SKILL.md must open with a '---' frontmatter fence")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("unterminated frontmatter: no closing '---'")
    raw, body = text[3:end], text[end + 4:]

    data: dict[str, Any] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in {">-", ">", "|", "|-"}:
            # Folded block: consume the indented continuation.
            i += 1
            chunk: list[str] = []
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith((" ", "\t"))):
                chunk.append(lines[i].strip())
                i += 1
            joined = " ".join(c for c in chunk if c)
            data[key] = re.sub(r"\s+", " ", joined).strip()
            continue
        if val.startswith("[") and val.endswith("]"):
            data[key] = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
        else:
            data[key] = val.strip().strip("'\"")
        i += 1
    return data, body


# --------------------------------------------------------------------------
# Registry records
# --------------------------------------------------------------------------


@dataclass
class SkillRecord:
    name: str
    path: str
    description: str
    stage: str = "shared"
    owner: str | None = None
    status: str = "stub"
    allowed_tools: list[str] = field(default_factory=list)
    consumes: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)
    credits: list[str] = field(default_factory=list)
    external_tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    body_lines: int = 0
    summary: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v not in (None, [], "")}


TRIGGER_RE = re.compile(r"Trigger on:\s*(.+?)(?:,?\s*or\s*/[a-z0-9-]+\.?)?$", re.I)


def _triggers_from_description(desc: str) -> list[str]:
    """Pull the quoted trigger phrases out of the description's 'Trigger on:' clause."""
    m = re.search(r"Trigger on:\s*(.*)$", desc, re.I)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def scan(skills_dir: Path = SKILLS_DIR) -> tuple[list[SkillRecord], list[str]]:
    """Read every skill on disk. Returns (records, problems)."""
    records: list[SkillRecord] = []
    problems: list[str] = []
    if not skills_dir.is_dir():
        return records, [f"{skills_dir} does not exist"]

    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        d = skill_md.parent
        try:
            fm, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"{skill_md}: {exc}")
            continue

        name = fm.get("name", "")
        if not name:
            problems.append(f"{skill_md}: frontmatter has no `name`")
            continue
        if name != d.name:
            problems.append(
                f"{skill_md}: frontmatter name {name!r} != directory {d.name!r} — "
                "the harness routes on the directory, so these must match"
            )
        desc = fm.get("description", "")
        if not desc:
            problems.append(f"{skill_md}: no `description` — the router has nothing to match on")

        body_lines = len(body.splitlines())
        if body_lines > 500:
            problems.append(
                f"{skill_md}: body is {body_lines} lines (limit 500) — move detail into reference/"
            )

        meta: dict[str, Any] = {}
        meta_path = d / "meta.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                problems.append(f"{meta_path}: invalid JSON ({exc})")
        else:
            problems.append(f"{d}: no meta.json — the orchestrator cannot route without a stage")

        stage = meta.get("stage", "shared")
        if stage not in VALID_STAGES:
            problems.append(f"{meta_path}: stage {stage!r} not in {sorted(VALID_STAGES)}")
        status = meta.get("status", "stub")
        if status not in VALID_STATUS:
            problems.append(f"{meta_path}: status {status!r} not in {sorted(VALID_STATUS)}")

        # Reference links in the body must resolve, or progressive disclosure is broken.
        refs = re.findall(r"\]\((reference/[^)]+)\)", body)
        for r in sorted(set(refs)):
            if not (d / r).is_file():
                problems.append(f"{skill_md}: links to missing {r}")

        tools = fm.get("allowed-tools", [])
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]

        records.append(
            SkillRecord(
                name=name,
                path=str(skill_md.parent).replace("\\", "/"),
                description=desc,
                stage=stage,
                owner=meta.get("owner"),
                status=status,
                allowed_tools=tools,
                consumes=meta.get("consumes", []),
                produces=meta.get("produces", []),
                credits=meta.get("credits", []),
                external_tools=meta.get("external_tools", []),
                triggers=_triggers_from_description(desc),
                references=sorted(set(refs)),
                body_lines=body_lines,
                summary=meta.get("summary"),
            )
        )
    return records, problems


def build_registry(
    skills_dir: Path = SKILLS_DIR, out: Path = REGISTRY
) -> tuple[dict[str, Any], list[str]]:
    """Generate registry.json. Returns (registry, problems)."""
    records, problems = scan(skills_dir)
    by_stage: dict[str, list[str]] = {}
    for r in records:
        by_stage.setdefault(r.stage, []).append(r.name)

    registry = {
        "version": 1,
        "generated_from": str(skills_dir).replace("\\", "/"),
        "n_skills": len(records),
        "by_stage": {k: sorted(v) for k, v in sorted(by_stage.items())},
        "by_status": {
            s: sorted(r.name for r in records if r.status == s)
            for s in sorted({r.status for r in records})
        },
        "skills": {r.name: r.to_json() for r in sorted(records, key=lambda r: (r.stage, r.name))},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return registry, problems


def check_handoffs(registry: dict[str, Any]) -> list[str]:
    """Lint the declared data flow: does anything produce what each skill consumes?

    Catches the failure this project is most exposed to — three people building
    three stages against an imagined interface. A `consumes` with no producer is
    a stage that will fail at run time, discovered now instead of on demo day.
    """
    # External inputs legitimately have no producing skill: they enter the pipeline
    # from outside it, written by a human or by the CLI. Without this the lint warns
    # about every stage that reads the problem definition, which trains people to
    # ignore the lint.
    produced: set[str] = {"problem.spec", "decisions.pending"}
    for s in registry["skills"].values():
        produced.update(s.get("produces", []))

    problems: list[str] = []
    for name, s in registry["skills"].items():
        for need in s.get("consumes", []):
            if need not in produced:
                problems.append(
                    f"{name} consumes {need!r} which no skill produces — "
                    "either a producer is missing or the key is misspelled"
                )
    orphans = [
        name for name, s in registry["skills"].items()
        if not s.get("produces") and s.get("status") != "planned"
    ]
    problems += [f"{n} declares no `produces` — nothing downstream can depend on it" for n in orphans]
    return problems


def format_list(registry: dict[str, Any], stage: str | None = None) -> str:
    rows = []
    marks = {"implemented": "[x]", "partial": "[~]", "stub": "[ ]", "planned": "[.]"}
    for name, s in registry["skills"].items():
        if stage and s.get("stage") != stage:
            continue
        rows.append(
            f"  {marks.get(s.get('status'), '[?]')} {name:<26} "
            f"{s.get('stage', ''):<18} {s.get('owner') or '-':<8} "
            f"{(s.get('summary') or s['description'])[:64]}"
        )
    header = (
        f"{registry['n_skills']} skills"
        + (f" (stage={stage})" if stage else "")
        + "\n  [x] implemented  [~] partial  [ ] stub  [.] planned\n"
    )
    return header + "\n".join(rows)
