---
name: output-contract
description: >-
  Package a finished result into exactly the artifact a grader accepts, and prove
  it survives the round trip before submitting. Treats format requirements as
  correctness requirements, validates with the grader's own checker rather than a
  reimplementation, and refuses to emit a partial artifact silently. Use when
  assembling a submission, when a validator rejects an output, or when a result is
  about to leave the machine. Trigger on: "submission format", "package the
  output", "will this be accepted", "round trip", "the validator rejected it",
  "assemble the submission", or /output-contract.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Output contract

A correct result in the wrong format scores zero. This stage has no scientific
content and it has decided real outcomes, which is exactly why it gets skimmed.

The characteristic failure is **not** a malformed file — that is caught
immediately. It is a file that parses cleanly, looks right when opened, and fails a
semantic check the grader runs and you did not.

## The round trip is the whole problem

Most output formats are lossy in ways that are invisible until something reads them
back. A pipeline holds a rich internal object; the format holds a projection of it.
Writing is fine. Reading is fine. **The composition of the two is where the
information dies**, and neither step reports a problem.

A concrete instance: a required artifact had to encode a molecule's connectivity,
and the file format stored coordinates and atom names but not bonds — those were
inferred on read. A generator emitted a correct structure under its own naming
conventions; renaming to the required convention made the file look right and left
the inferred connectivity wrong. Every visual check passed. The grader's semantic
check did not.

The general rule: **for every semantic property the grader checks, write the file,
read it back with an independent reader, and verify the property survived.** Not
the object you held in memory — the object that comes back off disk.

```python
def round_trip_check(obj, write, read, checks):
    """Write, read back with an independent reader, verify each property survived."""
    path = write(obj)
    recovered = read(path)
    return {name: fn(obj, recovered) for name, fn in checks.items()}
```

Independence matters. A reader that shares code with the writer inherits its
assumptions and will confirm anything the writer believes.

## Use the grader's validator

If the task ships a validator, **run that one**. Not a reimplementation, not a
careful reading of the specification.

A specification describes intent. The validator is the thing that actually decides,
and where they disagree the validator wins. Vendor it into the repo, pin its
version, and make it the only gate through which an artifact may be produced.

If no validator ships, write one from the specification and treat its disagreements
with your intuition as bugs in your intuition until proven otherwise.

## The checklist

Derive this from `problem.spec`'s output contract and verify each mechanically —
not by inspection, because inspection is what misses these:

| Class | Examples | Failure mode if missed |
|---|---|---|
| **Completeness** | one artifact per item, none extra | Missing items score as worst-case |
| **Naming** | exact identifier form, extension, case | Silent non-match, item scored as absent |
| **Structure** | container layout, nesting, flat vs foldered | Rejected wholesale |
| **Internal labelling** | required names for parts of the artifact | Grader cannot locate what it scores |
| **Semantic** | properties that must survive the round trip | The silent one |
| **Encoding** | line endings, character set, numeric precision | Intermittent and maddening |

Completeness deserves its own emphasis: **count**. The most common submission
defect is the wrong number of artifacts, because a few items failed upstream and
the packaging step did not notice. Compare against the authoritative item count,
not against how many files happen to exist.

## Refuse to emit partial output silently

If items are missing, the packaging step must fail loudly and require an explicit
override to proceed.

A partial submission is sometimes the right call under a deadline — but it must be
a decision someone made, not a state the pipeline drifted into. Make the override
explicit, and make it record what was missing and why.

```python
def assemble(items, expected_n, allow_partial=False):
    missing = expected_n - len(items)
    if missing and not allow_partial:
        raise SystemExit(
            f"refusing to package: {missing} of {expected_n} items missing. "
            "Re-run them, or pass allow_partial to submit incomplete on purpose."
        )
```

## Workflow

1. Read `problem.spec` for the output contract: format, naming, structure, and
   every semantic requirement. Read the validator's source if one exists — it is
   more authoritative than the prose describing it.
2. Read `method.rescued_selection` for the final choice per item.
3. Build the checklist above from the contract.
4. Convert one item and round-trip it against every semantic check. Fix before
   scaling — a conversion bug repeated across every item is the same bug, and
   finding it once is cheaper.
5. Convert all items. Count them against the authoritative total.
6. Run the grader's validator over the assembled artifact. Not over a sample.
7. Emit `method.submission` and `method.format_report`.

## Do a dry run early

Assemble and validate a submission the first day you have any output at all, even
if the contents are terrible.

The point is not the score. It is that every format problem surfaces while it is
cheap to fix, rather than in the last hour when the pipeline is also being changed.
A dry run costs an hour and it removes an entire class of deadline failure.

## Guard rails

- **Round-trip every semantic property** with an independent reader. The in-memory
  object is not evidence about the file.
- **Run the grader's own validator.** A reimplementation agrees with you, which is
  the problem.
- **Count artifacts against the authoritative item count**, not against the
  directory listing.
- **Never emit partial output without an explicit override** that records what is
  missing.
- **Validate the assembled container**, not a sample of its contents. Packaging
  introduces its own failures.
- **Pin the validator's version.** A validator that changed between your check and
  the submission checked nothing.
- **Dry-run the whole path early**, with bad content, before it matters.

## Anti-patterns

- **Verifying the in-memory object** and assuming the file matches it.
- **Reading the specification instead of running the validator.** Where they
  differ, the validator decides.
- **Renaming or relabelling to satisfy a check** without verifying the underlying
  property survived. The rename makes it look right and fixes nothing.
- **Validating one file and packaging a thousand.**
- **Shipping whatever files exist** because the count was never checked.
- **Leaving format work until the end**, when it competes with everything else for
  the last hours.
- **Using the writer's own reader to confirm the writer.** Shared assumptions, no
  independent check.

## Handoff

`method.submission` — the assembled artifact, validated — and
`method.format_report`, listing every check run, the item count against the
expected total, the validator's version and output, and any override that was
exercised.

`method.format_report` is what makes a rejection diagnosable. When a submission
comes back refused, the difference between a five-minute fix and an afternoon is
whether anyone recorded what was verified before it went out.
