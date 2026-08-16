#!/usr/bin/env python
"""Layer-1 evaluation for skills: is this skill structurally sound?

`reagent.skills.check_handoffs` already asks the one cross-skill question that
matters — does anything produce what each skill consumes. This adds the checks
that catch the *other* Layer-1 failure: a skill that parses, connects, and is
still wrong, because its prose and its contract have drifted apart.

The check worth having is DRIFT. A SKILL.md is read by an agent; meta.json is
read by the orchestrator. Nothing keeps them honest about each other, so a
`produces` key can be renamed in one and not the other and every mechanical
check still passes. Both files look fine. The handoff silently stops happening.

Severities:
    ERROR  contract or structure is broken; the skill cannot be trusted
    WARN   house-style drift; readable but degrading
    INFO   observation, no action implied

Exit 1 on any ERROR, so this can gate a commit.

    .venv/bin/python eval/skill_lint.py .claude/skills
    .venv/bin/python eval/skill_lint.py <dir> --strict   # WARN also fails
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Sections the house style expects once a skill claims to be implemented.
#
# Calibrated against the skills already marked implemented upstream, not against
# what a linter author finds tidy. Only "Guard rails" is universal. An earlier
# version of this file also required "## Handoff" and reported 28 errors on a
# working tree -- but Handoff is a Stage 2/3 stub convention, and shared skills
# like data-materialize and kg-visualize describe their outputs in prose
# instead. A linter that fires on healthy code gets muted, and then it catches
# nothing.
REQUIRED_SECTIONS = ["Guard rails"]
EXPECTED_SECTIONS = ["Guard rails", "Anti-patterns"]

# Keys that legitimately have no producing skill because they enter the graph
# from outside it. `problem.spec` is the ProblemSpec the CLI scaffolds, and it is
# consumed by seven skills; flagging it as a broken edge is noise.
EXTERNAL_INPUTS = {"problem.spec"}

# Observed band across upstream's implemented skills (126-200 lines).
IMPLEMENTED_MIN_LINES = 110
IMPLEMENTED_MAX_LINES = 260

MIN_TRIGGERS = 4

STUB_MARKERS = [
    "Contract-complete stub",
    "replace the body, keep the interface",
    "TODO",
    "FIXME",
]


@dataclass
class Finding:
    severity: str
    skill: str
    check: str
    message: str


@dataclass
class Skill:
    name: str
    path: Path
    frontmatter: dict
    body: str
    meta: dict
    lines: int
    errors: list[str] = field(default_factory=list)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Minimal YAML frontmatter reader — only the scalar/block forms skills use.

    Deliberately not a YAML dependency: this must run in a bare checkout, and
    the frontmatter grammar here is three keys deep at most.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end], text[end + 4 :]

    fm: dict[str, str] = {}
    key, buf = None, []
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            if key:
                fm[key] = " ".join(buf).strip()
            key = m.group(1)
            val = m.group(2).strip()
            buf = [] if val in (">-", ">", "|", "|-") else [val]
        elif key:
            buf.append(line.strip())
    if key:
        fm[key] = " ".join(buf).strip()
    return fm, body


def triggers_from(description: str) -> list[str]:
    """Pull the quoted phrases out of a `Trigger on: "a", "b", or /skill.` clause."""
    m = re.search(r"Trigger on:(.*)", description, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    return [t.strip().lower() for t in re.findall(r'"([^"]+)"', m.group(1))]


def load(skill_dir: Path) -> Skill | None:
    sk_path = skill_dir / "SKILL.md"
    meta_path = skill_dir / "meta.json"
    if not sk_path.exists():
        return None
    text = sk_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    meta, errs = {}, []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"meta.json is not valid JSON: {e}")
    else:
        errs.append("meta.json is missing")
    return Skill(skill_dir.name, skill_dir, fm, body, meta, len(text.splitlines()), errs)


# --------------------------------------------------------------------------
# per-skill checks
# --------------------------------------------------------------------------


def check_structure(s: Skill) -> list[Finding]:
    out = [Finding("ERROR", s.name, "load", e) for e in s.errors]
    for key in ("name", "description", "allowed-tools"):
        if not s.frontmatter.get(key):
            out.append(Finding("ERROR", s.name, "frontmatter", f"missing `{key}`"))
    fm_name = s.frontmatter.get("name")
    if fm_name and fm_name != s.name:
        out.append(
            Finding("ERROR", s.name, "frontmatter",
                    f"name `{fm_name}` does not match directory `{s.name}` — the orchestrator "
                    "resolves skills by directory, so this skill is unreachable under its own name")
        )
    for key in ("stage", "owner", "status", "consumes", "produces"):
        if key not in s.meta and not s.errors:
            out.append(Finding("ERROR", s.name, "meta", f"meta.json missing `{key}`"))
    return out


def check_handoff_drift(s: Skill) -> list[Finding]:
    """The core check: does the prose name every key the contract promises?

    An agent finishing this skill reads the Handoff section to know what to
    write. If meta.json promises `stage3.pool_oracle` and the prose never says
    so, the agent does not produce it, the next stage blocks, and no mechanical
    check anywhere notices — both files are individually valid.
    """
    out: list[Finding] = []
    produces = s.meta.get("produces") or []
    if not produces:
        return out

    def names(text: str, key: str) -> bool:
        # prose often shortens `stage3.pose_pool` to `pose_pool`, so accept either
        return key in text or bool(re.search(rf"\b{re.escape(key.split('.')[-1])}\b", text))

    # WARN, not ERROR. The body may describe an output perfectly well in prose
    # without writing the literal contract key -- kg-visualize says it renders an
    # interactive graph without ever typing `viz.kg_html`. Naming the key is
    # better, because it is what the orchestrator keys on and it removes a
    # mapping the agent would otherwise have to guess. But 17 of 20 upstream
    # skills do it this way, so treating it as fatal would fail a healthy tree.
    for key in produces:
        if not names(s.body, key):
            out.append(
                Finding("WARN", s.name, "produces",
                        f"meta.json promises `{key}` but the body never names it — "
                        "an agent must infer which described artifact this key refers to")
            )

    # WARN: there IS a Handoff section but it is incomplete. Weaker signal --
    # the output may be described adequately elsewhere in the body.
    m = re.search(r"^##+\s*Handoff\s*$(.*?)(?=^##\s|\Z)", s.body, re.MULTILINE | re.DOTALL)
    if m:
        for key in produces:
            if names(s.body, key) and not names(m.group(1), key):
                out.append(
                    Finding("WARN", s.name, "handoff",
                            f"`{key}` is described in the body but omitted from the Handoff "
                            "section, which is where the next stage looks")
                )
    return out


def check_consumes_mentioned(s: Skill) -> list[Finding]:
    """Inputs should appear somewhere in the body, or the skill ignores them."""
    out = []
    for key in s.meta.get("consumes") or []:
        tail = key.split(".")[-1]
        if key not in s.body and not re.search(rf"\b{re.escape(tail)}\b", s.body):
            out.append(
                Finding("WARN", s.name, "consumes",
                        f"declares it consumes `{key}` but the body never mentions it — "
                        "either use it or drop it from the contract")
            )
    return out


def check_status_honesty(s: Skill) -> list[Finding]:
    out: list[Finding] = []
    status = s.meta.get("status")
    body = s.body

    if status == "implemented":
        for marker in STUB_MARKERS:
            if marker.lower() in body.lower():
                out.append(Finding("ERROR", s.name, "status",
                                   f"marked implemented but still contains stub marker {marker!r}"))
        for sec in REQUIRED_SECTIONS:
            if not re.search(rf"^##+\s*{re.escape(sec)}", body, re.MULTILINE):
                out.append(Finding("ERROR", s.name, "sections",
                                   f"marked implemented but has no `## {sec}` section"))
        for sec in EXPECTED_SECTIONS:
            if not re.search(rf"^##+\s*{re.escape(sec)}", body, re.MULTILINE):
                out.append(Finding("WARN", s.name, "sections",
                                   f"implemented skill has no `## {sec}` section"))
        if s.lines < IMPLEMENTED_MIN_LINES:
            out.append(Finding("WARN", s.name, "length",
                               f"{s.lines} lines — below the {IMPLEMENTED_MIN_LINES}-line floor "
                               "seen in implemented skills; likely still thin"))
        elif s.lines > IMPLEMENTED_MAX_LINES:
            out.append(Finding("WARN", s.name, "length",
                               f"{s.lines} lines — above {IMPLEMENTED_MAX_LINES}; consider moving "
                               "detail into reference/"))
    elif status == "stub":
        out.append(Finding("INFO", s.name, "status", "stub — body not written yet"))
    return out


def check_triggers(s: Skill) -> list[Finding]:
    out = []
    trig = triggers_from(s.frontmatter.get("description", ""))
    if not trig:
        out.append(Finding("ERROR", s.name, "triggers",
                           "description has no `Trigger on:` clause, so the skill will not fire"))
    elif len(trig) < MIN_TRIGGERS:
        out.append(Finding("WARN", s.name, "triggers",
                           f"only {len(trig)} trigger phrases (expected >= {MIN_TRIGGERS})"))
    if f"/{s.name}" not in s.frontmatter.get("description", ""):
        out.append(Finding("WARN", s.name, "triggers",
                           f"description does not list the explicit `/{s.name}` invocation"))
    return out


def check_reference_links(s: Skill) -> list[Finding]:
    """A dead reference link is worse than none: it implies detail that is absent."""
    out = []
    for target in re.findall(r"\]\((reference/[^)#]+)\)", s.body):
        if not (s.path / target).exists():
            out.append(Finding("ERROR", s.name, "links", f"broken reference link `{target}`"))
    ref_dir = s.path / "reference"
    if ref_dir.is_dir():
        for f in sorted(ref_dir.glob("*.md")):
            if f"reference/{f.name}" not in s.body:
                out.append(Finding("WARN", s.name, "links",
                                   f"`reference/{f.name}` exists but nothing links to it"))
    return out


# --------------------------------------------------------------------------
# cross-skill checks
# --------------------------------------------------------------------------


def check_graph(skills: list[Skill]) -> list[Finding]:
    out: list[Finding] = []
    produced: dict[str, list[str]] = defaultdict(list)
    consumed: dict[str, list[str]] = defaultdict(list)
    for s in skills:
        for k in s.meta.get("produces") or []:
            produced[k].append(s.name)
        for k in s.meta.get("consumes") or []:
            consumed[k].append(s.name)

    for key, consumers in sorted(consumed.items()):
        if key in produced:
            continue
        if key in EXTERNAL_INPUTS:
            out.append(Finding("INFO", f"{len(consumers)} skills", "graph",
                               f"`{key}` enters from outside the skill graph (allowlisted)"))
        else:
            out.append(Finding("ERROR", ", ".join(consumers), "graph",
                               f"consumes `{key}` which no skill produces — this stage cannot run"))
    for key, producers in sorted(produced.items()):
        if key not in consumed:
            out.append(Finding("INFO", ", ".join(producers), "graph",
                               f"produces `{key}` which nothing consumes (terminal output?)"))
    for key, producers in sorted(produced.items()):
        if len(producers) > 1:
            out.append(Finding("WARN", ", ".join(producers), "graph",
                               f"`{key}` is produced by {len(producers)} skills — ambiguous ownership"))
    return out


def check_trigger_collisions(skills: list[Skill]) -> list[Finding]:
    """Two skills claiming the same phrase makes dispatch a coin toss."""
    owners: dict[str, list[str]] = defaultdict(list)
    for s in skills:
        for t in triggers_from(s.frontmatter.get("description", "")):
            owners[t].append(s.name)
    return [
        Finding("ERROR", ", ".join(names), "triggers",
                f"trigger phrase {phrase!r} is claimed by {len(names)} skills — dispatch is ambiguous")
        for phrase, names in sorted(owners.items())
        if len(names) > 1
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skills_dir", type=Path, nargs="?", default=Path(".claude/skills"))
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    ap.add_argument("--only", nargs="+", help="limit per-skill checks to these skill names")
    ap.add_argument("--quiet", action="store_true", help="suppress INFO")
    ap.add_argument(
        "--graph-from", type=Path, action="append", default=[],
        help="additional skill dirs to resolve the contract graph against. Needed when "
             "linting a subset: a Stage 3 skill consumes Stage 1/2 keys, so without the "
             "rest of the tree every input looks like a broken edge.",
    )
    args = ap.parse_args()

    if not args.skills_dir.is_dir():
        print(f"no such directory: {args.skills_dir}")
        return 1

    skills = [s for d in sorted(args.skills_dir.iterdir()) if d.is_dir() and (s := load(d))]
    if not skills:
        print(f"no skills found under {args.skills_dir}")
        return 1

    # Graph checks see the union; per-skill checks see only what was asked for.
    graph_skills = list(skills)
    seen = {s.name for s in skills}
    for extra in args.graph_from:
        if not extra.is_dir():
            print(f"--graph-from: no such directory: {extra}")
            return 1
        for d in sorted(extra.iterdir()):
            if d.is_dir() and d.name not in seen and (s := load(d)):
                graph_skills.append(s)
                seen.add(d.name)

    findings: list[Finding] = []
    for s in skills:
        if args.only and s.name not in args.only:
            continue
        for fn in (check_structure, check_handoff_drift, check_consumes_mentioned,
                   check_status_honesty, check_triggers, check_reference_links):
            findings.extend(fn(s))
    findings.extend(check_graph(graph_skills))
    findings.extend(check_trigger_collisions(graph_skills))

    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (order[f.severity], f.skill, f.check))

    n_err = sum(1 for f in findings if f.severity == "ERROR")
    n_warn = sum(1 for f in findings if f.severity == "WARN")

    print(f"linted {len(skills)} skills under {args.skills_dir}\n")
    for f in findings:
        if args.quiet and f.severity == "INFO":
            continue
        print(f"  {f.severity:<5} [{f.check}] {f.skill}: {f.message}")

    print(f"\n  {n_err} error(s), {n_warn} warning(s)")
    if n_err:
        return 1
    if args.strict and n_warn:
        print("  --strict: warnings are failures")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
