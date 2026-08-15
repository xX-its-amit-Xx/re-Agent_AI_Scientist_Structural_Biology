# Extraction schemas

Ready-made `--output-schema` payloads for Paperclip's `map` command, one per claim
type, each with the field-by-field prompt that makes it work. Copy one, adapt the
vocabulary to your problem, and run it. Do not write a new schema from scratch when
one of these is close — the failure modes below were paid for once already.

Mechanics, from [paperclip-cli.md](paperclip-cli.md): `map` validates each worker's
output against the schema at the tool layer, allows **one** correction attempt, then
marks that paper failed. So a strict schema costs coverage and buys clean data, and
the trade is worth making because a single confidently-wrong number poisons every
downstream stage that reads the graph as fact.

```
map --from s_YYYY --worker structured-extraction -j 32 \
  --output-schema '<one of the schemas below, as a single-line JSON string>' \
  "<the matching prompt below>"
```

## The five design rules

**One concept per schema.** A schema that extracts binding affinities *and* pocket
residues *and* method choices returns mush for all three. The worker has a fixed
attention budget per paper and splitting it across unrelated concepts degrades
every one of them. Run three maps over the same result set instead — `map` is
cheap and the result set is reusable.

**`additionalProperties: false`, and every field explicitly nullable rather than
optional.** A worker that is *allowed* to omit a field will omit the hard one, and
you will not be able to distinguish "the paper does not say" from "the worker did
not look". Make every field `required` and give the hard ones a null branch in
their type, so "absent" becomes an explicit, countable answer.

**Require a line range for every assertion.** This is what produces checkable
citations, and requiring it measurably suppresses invention — a worker that must
name the lines supporting a number is far less likely to produce a number that is
not there. It is also what lets Step 4 of the skill spot-check by hand.

**Require polarity.** Whether the paper *supports*, *contradicts*, or makes *no
claim* about the assertion. The contradictions are what make the graph worth
building, and a schema without a polarity field silently converts every
disagreement in the literature into an agreement.

**Write the prompt field by field.** A vague prompt against a strict schema
produces confidently-wrong values, which is worse than a validation failure — a
failure is visible in the map's failed count, a wrong value is not. Every prompt
below names each field, states its unit and its allowed values, and says explicitly
what to do when the paper does not contain it.

Two shared conventions used by all five schemas:

- The top level is always an object with a single `assertions` array, plus a
  `paper_has_no_relevant_content` boolean. An empty array plus that flag set to
  true is a *result* — it tells you the search returned an off-topic paper — while
  an empty array with the flag false means the worker found the topic but could not
  extract a structured claim.
- `line_range` matches `^L\d+(-L\d+)?$`, matching Paperclip's `content.lines`
  anchors. See [citation-hygiene.md](citation-hygiene.md) for how it becomes a
  locator like `pmc:PMC12690452#L45-L52`.

## (a) Binding or affinity measurement

Maps to `Predicate.BINDS` (Protein or Pocket to Compound or Fragment) plus
`Predicate.MEASURED_IN` to an `Assay` node.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["assertions", "paper_has_no_relevant_content"],
  "properties": {
    "paper_has_no_relevant_content": {"type": "boolean"},
    "assertions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "target_name", "target_accession", "ligand_name", "ligand_identifier",
          "ligand_smiles", "measurement_type", "value", "unit", "relation",
          "assay_format", "organism_or_construct", "temperature_c", "ph",
          "polarity", "line_range", "verbatim_span"
        ],
        "properties": {
          "target_name": {"type": "string", "minLength": 2},
          "target_accession": {
            "type": ["string", "null"],
            "description": "UniProt accession if the paper states one; null otherwise. Do not infer."
          },
          "ligand_name": {"type": "string", "minLength": 1},
          "ligand_identifier": {
            "type": ["string", "null"],
            "description": "ChEMBL id, PDB chemical component id, CAS number, or the paper's own compound label."
          },
          "ligand_smiles": {"type": ["string", "null"]},
          "measurement_type": {
            "type": "string",
            "enum": ["Kd", "Ki", "IC50", "EC50", "Ka", "Kb", "pIC50", "pEC50",
                     "percent_inhibition", "percent_activation", "Tm_shift", "other"]
          },
          "value": {"type": ["number", "null"]},
          "unit": {
            "type": ["string", "null"],
            "enum": ["M", "mM", "uM", "nM", "pM", "log_molar", "percent", "celsius", null]
          },
          "relation": {"type": "string", "enum": ["=", "<", ">", "<=", ">=", "approx"]},
          "assay_format": {
            "type": ["string", "null"],
            "description": "e.g. 'radioligand displacement', 'SPR', 'ITC', 'TR-FRET', 'cell-based reporter'."
          },
          "organism_or_construct": {
            "type": ["string", "null"],
            "description": "Species and construct boundaries if stated, e.g. 'human LBD residues 142-434'."
          },
          "temperature_c": {"type": ["number", "null"]},
          "ph": {"type": ["number", "null"]},
          "polarity": {"type": "string", "enum": ["supports", "contradicts", "no_claim"]},
          "line_range": {"type": "string", "pattern": "^L\\d+(-L\\d+)?$"},
          "verbatim_span": {
            "type": "string",
            "minLength": 10,
            "description": "Copied exactly from the cited lines. No paraphrase."
          }
        }
      }
    }
  }
}
```

Prompt:

```
Extract every reported binding or potency measurement between a protein and a small
molecule. One array element per (protein, ligand, measurement) triple. If the same
pair is measured in two assays, emit two elements.

target_name: the protein as the paper names it.
target_accession: a UniProt accession ONLY if the paper prints one. Never look it up
  or infer it from the protein name. Otherwise null.
ligand_name: the compound as named in the text, including the paper's internal label
  (for example "compound 12b") if that is all it has.
ligand_identifier: any database identifier the paper gives - ChEMBL id, PDB chemical
  component id, CAS number. Otherwise the paper's internal label. Otherwise null.
ligand_smiles: only if the paper prints a SMILES string. Do not generate one from a
  drawn structure or a name.
measurement_type: pick from the enum. Use the paper's own term - do NOT convert an
  IC50 into a Ki, or an EC50 into a Kd. They are different quantities.
value: the number as printed. If the paper reports a range, use the midpoint and say
  so in verbatim_span. If it reports only a plot with no number, value is null.
unit: as printed. If the paper reports pIC50 or pEC50, set measurement_type to that
  and unit to "log_molar" - do not convert.
relation: "=" unless the paper prints an inequality (">10 uM" is relation ">").
assay_format: the assay as described in Methods, in the paper's words.
organism_or_construct: species and residue boundaries if stated; else null.
temperature_c, ph: only if stated in Methods; else null.
polarity: "supports" if the paper asserts this measurement as its own result;
  "contradicts" if the paper reports it in order to dispute a previously published
  value; "no_claim" if it is cited as background from another paper.
line_range: the L-numbered lines containing the value, as "L120" or "L118-L124".
verbatim_span: the exact text from those lines. Copy, do not summarise.

If the paper contains no such measurement, return an empty assertions array and set
paper_has_no_relevant_content according to whether the paper is about this topic at all.
```

**Never normalise units in the schema.** Store the value and unit as printed and
convert in your own code, where the conversion is auditable and reversible. Workers
asked to convert produce off-by-a-thousand errors, and a nanomolar affinity stored
as micromolar is exactly the confidently-wrong number this whole apparatus exists
to prevent. When you do convert to `affinity_nm` for the edge `attrs`, keep
`affinity_raw` and `affinity_unit_raw` beside it.

## (b) Structural observation about a binding site or residue

Maps to `Pocket` and `Residue` nodes with `Predicate.POCKET_LINED_BY`, and to
`Predicate.CO_CRYSTALLIZED_WITH` when a complex is described.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["assertions", "paper_has_no_relevant_content"],
  "properties": {
    "paper_has_no_relevant_content": {"type": "boolean"},
    "assertions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "protein_name", "structure_id", "structure_method", "resolution_angstrom",
          "residue_name", "residue_number", "numbering_basis", "interaction_type",
          "partner", "distance_angstrom", "functional_consequence", "evidence_basis",
          "polarity", "line_range", "verbatim_span"
        ],
        "properties": {
          "protein_name": {"type": "string", "minLength": 2},
          "structure_id": {
            "type": ["string", "null"],
            "description": "PDB entry id if the observation comes from a deposited structure."
          },
          "structure_method": {
            "type": ["string", "null"],
            "enum": ["X-ray", "cryo-EM", "NMR", "predicted", "docking", "MD", "none_stated", null]
          },
          "resolution_angstrom": {"type": ["number", "null"]},
          "residue_name": {
            "type": ["string", "null"],
            "description": "Three-letter or one-letter code as printed, e.g. 'Ser' or 'S'."
          },
          "residue_number": {"type": ["integer", "null"]},
          "numbering_basis": {
            "type": ["string", "null"],
            "description": "Which numbering the residue number refers to: 'UniProt', 'PDB auth', 'construct', or null if the paper does not say. This is the field people omit and it makes every residue number ambiguous."
          },
          "interaction_type": {
            "type": ["string", "null"],
            "enum": ["hydrogen_bond", "salt_bridge", "pi_stacking", "pi_cation",
                     "hydrophobic", "halogen_bond", "water_mediated", "covalent",
                     "steric_clash", "none_stated", null]
          },
          "partner": {
            "type": ["string", "null"],
            "description": "What the residue contacts: a ligand name, a ligand moiety, another residue, or a metal."
          },
          "distance_angstrom": {"type": ["number", "null"]},
          "functional_consequence": {
            "type": ["string", "null"],
            "description": "What the paper says this residue does, in one clause, e.g. 'mutation to alanine abolishes activation'."
          },
          "evidence_basis": {
            "type": "string",
            "enum": ["experimental_structure", "mutagenesis", "computational_model",
                     "docking", "inference_from_homolog", "assertion_without_data"]
          },
          "polarity": {"type": "string", "enum": ["supports", "contradicts", "no_claim"]},
          "line_range": {"type": "string", "pattern": "^L\\d+(-L\\d+)?$"},
          "verbatim_span": {"type": "string", "minLength": 10}
        }
      }
    }
  }
}
```

Prompt:

```
Extract every specific claim the paper makes about a residue in a binding site.
One array element per (residue, interaction) claim. A sentence naming four residues
in one pocket produces four elements.

protein_name: as named in the paper.
structure_id: the PDB entry id if the claim is read off a deposited structure;
  null if it comes from a model, a docking run, or an unsupported assertion.
structure_method, resolution_angstrom: as stated in the text or the table; else null.
residue_name, residue_number: exactly as printed. Do NOT renumber.
numbering_basis: state which numbering the number is in. If the paper does not say,
  use null - do not guess "UniProt". A residue number without its basis is unusable
  downstream, and recording that the paper omitted it is itself informative.
interaction_type: pick from the enum only if the paper names the interaction. If it
  says only "lines the pocket", use "none_stated".
partner: what the residue contacts, in the paper's words, including the ligand moiety
  if specified ("the phenyl ring of compound 4").
distance_angstrom: only if a distance is printed.
functional_consequence: one clause, from the paper. Null if it only describes geometry.
evidence_basis: how the claim is supported. Use "assertion_without_data" when the
  paper states it with no structure, mutation, or calculation of its own - this is a
  common and important case, and mislabelling it as experimental is the worst error
  you can make here.
polarity: "contradicts" if this observation disputes a previously published
  assignment for the same residue.
line_range, verbatim_span: as above.
```

The `numbering_basis` field looks pedantic and is the most valuable field in the
schema. Residue numbering differs between a construct, the PDB author numbering, and
the UniProt sequence, and a pocket map assembled from papers that use different
conventions is worse than no map — it will place restraints on the wrong residues.
Extracting the basis, including the fact that it was not stated, is what makes the
map reconcilable later.

## (c) Method performance claim with its evaluation set

Maps to `Method` and `Assay` (benchmark) nodes with `Predicate.EVALUATED_ON` and
`Predicate.OUTPERFORMS`. This is the Stage 0 workhorse.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["assertions", "paper_has_no_relevant_content"],
  "properties": {
    "paper_has_no_relevant_content": {"type": "boolean"},
    "assertions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "method_name", "method_version", "task", "metric_name", "metric_value",
          "metric_units", "eval_set_name", "eval_set_size", "split_type",
          "baseline_name", "baseline_value", "is_self_reported", "trained_on",
          "polarity", "line_range", "verbatim_span"
        ],
        "properties": {
          "method_name": {"type": "string", "minLength": 2},
          "method_version": {"type": ["string", "null"]},
          "task": {
            "type": "string",
            "description": "What was predicted, in the paper's terms, e.g. 'protein-ligand complex prediction'."
          },
          "metric_name": {"type": "string", "minLength": 2},
          "metric_value": {"type": ["number", "null"]},
          "metric_units": {
            "type": ["string", "null"],
            "description": "e.g. 'angstrom', 'fraction', 'percent', 'spearman_rho', or null for a dimensionless score."
          },
          "eval_set_name": {
            "type": ["string", "null"],
            "description": "The named benchmark or the paper's description of its held-out set. A metric with no evaluation set is uncomparable - record null and let the consumer discount it."
          },
          "eval_set_size": {"type": ["integer", "null"]},
          "split_type": {
            "type": ["string", "null"],
            "enum": ["random", "temporal", "scaffold", "sequence_identity",
                     "cluster", "blind_challenge", "not_stated", null]
          },
          "baseline_name": {"type": ["string", "null"]},
          "baseline_value": {"type": ["number", "null"]},
          "is_self_reported": {
            "type": "boolean",
            "description": "True if the authors developed the method they are reporting on."
          },
          "trained_on": {
            "type": ["string", "null"],
            "description": "The training corpus as described, including whether it is proprietary."
          },
          "polarity": {"type": "string", "enum": ["supports", "contradicts", "no_claim"]},
          "line_range": {"type": "string", "pattern": "^L\\d+(-L\\d+)?$"},
          "verbatim_span": {"type": "string", "minLength": 10}
        }
      }
    }
  }
}
```

Prompt:

```
Extract every quantitative performance claim about a computational method. One array
element per (method, metric, evaluation set) triple. A table of five methods on two
metrics produces ten elements.

method_name, method_version: as printed, including a version or release if given.
task: what was predicted, in the paper's own terms.
metric_name: the metric as named. Do not translate one metric into another.
metric_value, metric_units: the number as printed and its unit. If only a figure
  shows it with no number in the text or table, metric_value is null.
eval_set_name: the benchmark's name, or the paper's description of its held-out set.
  If the paper reports a number with no stated evaluation set, use null - that is a
  real and important finding about the paper.
eval_set_size: number of items evaluated, if stated.
split_type: how train and test were separated. Use "not_stated" when the paper is
  silent; this distinguishes an omission from a random split.
baseline_name, baseline_value: the comparator this claim is made against, if any.
is_self_reported: true when the authors are reporting on their own method. Almost
  all headline numbers are self-reported and downstream needs to know.
trained_on: the training corpus, including whether the paper describes it as
  proprietary, internal, or unavailable. This decides whether a gap is closeable by
  method or only by data.
polarity: "contradicts" when the paper reports a number that disputes a previously
  published claim about the same method on the same benchmark - reproduction
  failures are exactly what we are looking for.
line_range, verbatim_span: as above.
```

`is_self_reported` and `split_type` are what let a downstream stage build an honest
benchmark table rather than a marketing table. A self-reported number on an unstated
split is not a benchmark, and the schema should force that to be visible rather than
leaving it to be inferred from the author list.

## (d) Negative or failed result

Maps to `Predicate.FAILS_ON` and `FindingKind.NEGATIVE`. The literature under-reports
these, which makes each one disproportionately valuable — the reference case's list
of eight refuted approaches was described by its own authors as more valuable than
the winning method, precisely because nobody publishes it.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["assertions", "paper_has_no_relevant_content"],
  "properties": {
    "paper_has_no_relevant_content": {"type": "boolean"},
    "assertions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "what_was_tried", "applied_to", "expected_outcome", "observed_outcome",
          "magnitude", "failure_mode", "authors_explanation", "was_it_the_paper_s_own_attempt",
          "n_attempts", "is_stated_as_failure", "polarity", "line_range", "verbatim_span"
        ],
        "properties": {
          "what_was_tried": {
            "type": "string",
            "minLength": 5,
            "description": "The method, parameter, or idea that did not work."
          },
          "applied_to": {
            "type": ["string", "null"],
            "description": "The system, dataset, or subpopulation it failed on. A failure without its context is not transferable."
          },
          "expected_outcome": {"type": ["string", "null"]},
          "observed_outcome": {"type": "string", "minLength": 5},
          "magnitude": {
            "type": ["string", "null"],
            "description": "The size of the failure as printed, e.g. 'RMSD rose from 3.9 to 24.6 angstrom', 'no improvement over baseline'."
          },
          "failure_mode": {
            "type": ["string", "null"],
            "enum": ["no_effect", "worse_than_baseline", "worked_on_subset_only",
                     "unstable_high_variance", "did_not_converge", "not_reproducible",
                     "computationally_infeasible", "data_insufficient", "other", null]
          },
          "authors_explanation": {"type": ["string", "null"]},
          "was_it_the_paper_s_own_attempt": {"type": "boolean"},
          "n_attempts": {"type": ["integer", "null"]},
          "is_stated_as_failure": {
            "type": "boolean",
            "description": "True if the paper frames it as a failure. False if it is buried in a limitations paragraph or a supplementary table while the abstract stays positive."
          },
          "polarity": {"type": "string", "enum": ["supports", "contradicts", "no_claim"]},
          "line_range": {"type": "string", "pattern": "^L\\d+(-L\\d+)?$"},
          "verbatim_span": {"type": "string", "minLength": 10}
        }
      }
    }
  }
}
```

Prompt:

```
Extract every reported failure, null result, or approach that did not work. Look
specifically in the Discussion, the Limitations section, and any supplementary
comparison table - negative results are rarely in the abstract.

what_was_tried: the method, parameter choice, or idea, specifically enough to avoid
  repeating it.
applied_to: the system, dataset, or subpopulation it failed on. A method that fails
  on fragments and works on drug-like molecules is not "a method that fails", and the
  scope is the entire value of the record.
expected_outcome, observed_outcome: what the authors expected and what happened.
magnitude: the size of the failure, with the numbers as printed if any.
failure_mode: pick from the enum. "worked_on_subset_only" is the most useful value
  and the easiest to miss - use it whenever the failure is scoped.
authors_explanation: their stated reason, if they give one. Do not supply your own.
was_it_the_paper_s_own_attempt: true if these authors ran it; false if they are
  reporting someone else's failure.
n_attempts: how many variants or replicates were tried, if stated.
is_stated_as_failure: true if the paper calls it a failure; false if it is only
  visible in a table or a hedged limitations sentence while the framing stays positive.
polarity: usually "supports" (the paper supports the claim that this failed). Use
  "contradicts" when the paper reports failing to reproduce a published success.
line_range, verbatim_span: as above. For a negative result the verbatim span matters
  more than usual, because the claim is unusual and will be challenged.
```

## (e) Dataset mention

Maps to a `Dataset` node carrying a `DataRef` (see
`reagent/contracts/data.py`), with `Predicate.HAS_DATA`,
`Predicate.DATASET_COVERS`, and `Predicate.DERIVED_FROM` to the paper. Stage 1
records **where the data lives and does not download it**; that is the `DataRef`
contract, and the fields below map onto it deliberately.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["assertions", "paper_has_no_relevant_content"],
  "properties": {
    "paper_has_no_relevant_content": {"type": "boolean"},
    "assertions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "dataset_title", "identifier", "identifier_kind", "url", "measures",
          "n_records", "file_format", "entities_covered", "access", "licence",
          "role_in_paper", "is_newly_deposited", "polarity", "line_range", "verbatim_span"
        ],
        "properties": {
          "dataset_title": {"type": "string", "minLength": 2},
          "identifier": {
            "type": ["string", "null"],
            "description": "The accession as printed: a DOI, a repository accession, a GitHub path, a competition slug."
          },
          "identifier_kind": {
            "type": ["string", "null"],
            "enum": ["doi", "zenodo", "figshare", "osf", "huggingface", "github",
                     "kaggle", "chembl", "bindingdb", "pdb", "geo", "supplementary_file",
                     "other", null]
          },
          "url": {"type": ["string", "null"]},
          "measures": {
            "type": "array",
            "items": {
              "type": "string",
              "enum": ["binding_affinity", "activity", "induction", "thermal_shift",
                       "structure", "enrichment", "property", "kinetics",
                       "selectivity_panel", "prediction", "other"]
            },
            "description": "May be empty if the paper does not say what is in it."
          },
          "n_records": {"type": ["integer", "null"]},
          "file_format": {
            "type": ["string", "null"],
            "enum": ["csv", "tsv", "parquet", "json", "sdf", "smiles", "pdb",
                     "mmcif", "fasta", "hdf5", "archive", "notebook", "other", null]
          },
          "entities_covered": {
            "type": ["string", "null"],
            "description": "Which proteins, compounds, or assays it covers, as described."
          },
          "access": {
            "type": "string",
            "enum": ["open", "registration", "api_key", "request", "restricted", "unknown"]
          },
          "licence": {"type": ["string", "null"]},
          "role_in_paper": {
            "type": "string",
            "enum": ["newly_generated_by_this_paper", "reused_as_training_data",
                     "reused_as_evaluation_data", "cited_as_background", "other"]
          },
          "is_newly_deposited": {"type": "boolean"},
          "polarity": {"type": "string", "enum": ["supports", "contradicts", "no_claim"]},
          "line_range": {"type": "string", "pattern": "^L\\d+(-L\\d+)?$"},
          "verbatim_span": {"type": "string", "minLength": 10}
        }
      }
    }
  }
}
```

Prompt:

```
Extract every dataset the paper deposits, uses, or cites. Check the Data
Availability statement, the Methods, and the references - most datasets are named in
one of those three places and nowhere else.

dataset_title: the name the paper uses for it.
identifier, identifier_kind: the accession exactly as printed. Never construct or
  complete an identifier - a fabricated DOI is unrecoverable downstream, and a null
  is fine.
url: only if printed in the paper.
measures: what the dataset contains, from the enum. Empty array if the paper does not say.
n_records, file_format: if stated; else null.
entities_covered: which proteins, compounds, or assays, as described.
access: "open" only if the paper says it is freely downloadable. Use "request" for
  "available from the authors on reasonable request", and "restricted" for
  proprietary or licence-limited data.
licence: as printed, e.g. "CC BY 4.0". Null if not stated.
role_in_paper: what the dataset was for. Distinguish training data from evaluation
  data - it decides whether a later comparison is contaminated.
is_newly_deposited: true if this paper is the deposit's source.
polarity: "no_claim" for a plain mention; "supports" when the dataset is offered as
  evidence for a claim.
line_range, verbatim_span: as above; the Data Availability statement is usually the
  right span.
```

"Available from the authors on reasonable request" must come through as
`access: "request"`, not `"open"`. `DataRef` will then require a `fetch_hint` before
it validates, which forces you to record what "request" actually means while you
still have the paper open — and that is the whole point of extracting it.

## After the map: turning output into a delta

Two rules from the skill that bind here.

**A null value is not a zero.** If `metric_value` or `value` comes back null, the
edge is either not written at all, or written with `Confidence.SPECULATIVE` and
`attrs["unmeasured"] = True`. Never substitute a plausible number, and never let a
null silently become the absence of the field.

**Spot-check five assertions by hand before merging.** Open the cited lines
(`grep -n -C 2 "<claimed term>" /papers/<ID>/content.lines`) and check the value, the
polarity, and that the verbatim span is actually verbatim. Record the hit rate as
`extraction_spot_check_accuracy` in the report metrics. Below about 0.8, fix the
schema or the prompt and re-run rather than shipping the graph.

The most common cause of a low spot-check rate is not the schema — it is a prompt
that names a field without stating its unit, its allowed values, or what to do when
the paper is silent. That is why every prompt above says "else null" explicitly, for
every nullable field.
