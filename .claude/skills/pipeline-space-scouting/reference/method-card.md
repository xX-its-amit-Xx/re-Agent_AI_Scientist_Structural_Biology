# MethodCard — the schema every scout subagent must return

One card per method. A scout subagent returns a JSON array of these and nothing
else: no prose summary, no commentary, no "here is what I found". The orchestrator's
context is the scarce resource in this stage, and cards are what survive
compaction. Prose does not.

A card is not a description of a method. It is **the record you need in order to
decide whether the method can be a candidate**, which is a much narrower and much
more demanding thing. Three fields carry most of that weight and are the three
most often faked: `performance[].eval_set`, `cost`, and `failure_modes`. A card
that is vague in those three is worse than no card, because it launders a guess
into the shape of a fact.

## Hard rules, before the schema

1. **Every performance number carries its evaluation set.** `eval_set` is
   required, non-nullable, and has a minimum length. There is no valid card with
   a bare number in it. See "Why performance without an eval set is rejected"
   below — this is the single rule that most improves Stage 0 output quality.
2. **Unknown is a value; unknown is not a blank.** Nullable fields exist so a
   scout can say "not recorded anywhere I looked" without either inventing a
   number or silently dropping the field. `"wall_seconds_per_item": null` with
   `"cost_notes": "no timing published; measure this yourself"` is a good card.
   `"wall_seconds_per_item": 30` sourced from vibes is a corrupt card.
3. **`verdict.candidate` may not be `true` while `cost` is unknown.** The skill's
   guard rail is "do not rank methods you have not costed". The schema encodes it:
   if hardware and either wall-clock or throughput are null, the verdict must be
   `false` with `blocking_reason` set to the missing cost information. A method
   the team cannot run, or cannot tell whether it can run, is not a candidate.
4. **`scout.queries` records the exact query strings used.** This is what makes a
   scouting pass reproducible and what lets a later run diff the landscape rather
   than rebuild it. A card with an empty `queries` array cannot be audited.
5. **Citations use the project's `SourceType` vocabulary verbatim** (from
   `src/reagent/contracts/report.py`), so a card converts into `Evidence` objects
   mechanically, with no mapping layer to get wrong.

## The schema (JSON Schema, Draft 2020-12)

`additionalProperties: false` throughout, every property listed in `required`,
every optional value expressed as an explicit `null` union. This is the same
discipline the Paperclip `map --output-schema` engine rewards (see
`.claude/skills/literature-harvest/reference/paperclip-cli.md`): a tight schema
costs coverage and buys clean data, and validation happens at the tool layer with
exactly one correction attempt, so loose schemas produce confidently-wrong
values rather than failures.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "reagent/stage0/method-card.schema.json",
  "title": "MethodCard",
  "description": "One computational method, costed and cited, as returned by a Stage 0 scout subagent.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "card_version", "node_id", "name", "version", "aliases", "one_line",
    "pipeline_position", "io", "performance", "cost", "licence", "maturity",
    "failure_modes", "alternative_to", "used_by", "citations", "scout",
    "verdict", "open_questions", "notes"
  ],
  "properties": {
    "card_version": { "const": "1.0.0" },

    "node_id": {
      "description": "Namespaced knowledge-graph id, matching reagent.contracts.kg.Node conventions.",
      "type": "string",
      "pattern": "^method:[a-z0-9][a-z0-9._+-]*$"
    },

    "name": { "type": "string", "minLength": 2 },

    "version": {
      "description": "The exact version evaluated. Null only if the source genuinely does not say, which is itself a finding.",
      "type": ["string", "null"]
    },

    "aliases": {
      "description": "Other names the same method travels under, so two scouts do not create two nodes.",
      "type": "array",
      "items": { "type": "string" }
    },

    "one_line": {
      "description": "What it does, mechanistically, in one sentence. Not marketing.",
      "type": "string",
      "minLength": 20,
      "maxLength": 400
    },

    "pipeline_position": {
      "type": "object",
      "additionalProperties": false,
      "required": ["step", "step_node_id", "role", "is_terminal"],
      "properties": {
        "step": {
          "description": "Which slot in a prediction pipeline this occupies. Drives Predicate.USED_IN.",
          "type": "string",
          "enum": [
            "problem_framing", "data_curation", "featurization", "templating",
            "sampling", "generation", "refinement", "scoring", "ranking_selection",
            "ensembling", "calibration", "postprocessing", "submission_packaging",
            "evaluation", "end_to_end"
          ]
        },
        "step_node_id": {
          "description": "PipelineStep node id, 'step:<slug>' matching the step value.",
          "type": "string",
          "pattern": "^step:[a-z0-9][a-z0-9._-]*$"
        },
        "role": {
          "description": "What it consumes from upstream and hands downstream, in prose.",
          "type": "string",
          "minLength": 15
        },
        "is_terminal": {
          "description": "True if this method alone produces a submittable output.",
          "type": "boolean"
        }
      }
    },

    "io": {
      "type": "object",
      "additionalProperties": false,
      "required": ["inputs", "outputs", "hard_requirements"],
      "properties": {
        "inputs": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/io_item" } },
        "outputs": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/io_item" } },
        "hard_requirements": {
          "description": "Things without which the method cannot run at all: an MSA, a pocket definition, a holo template, a labelled training set of a given size, an upstream candidate pool.",
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },

    "performance": {
      "description": "Zero or more claims. Empty array is legal and honest; a claim without an eval_set is not.",
      "type": "array",
      "items": { "$ref": "#/$defs/performance_claim" }
    },

    "cost": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "hardware", "wall_seconds_per_item", "throughput_per_hour",
        "peak_memory_gb", "usd_per_item", "credit_pool", "requires_network",
        "measured", "measurement_basis", "cost_notes"
      ],
      "properties": {
        "hardware": {
          "description": "Minimum viable hardware, e.g. '1x A100 40GB', 'CPU, 8 cores', 'hosted API only'.",
          "type": ["string", "null"]
        },
        "wall_seconds_per_item": { "type": ["number", "null"], "minimum": 0 },
        "throughput_per_hour": { "type": ["number", "null"], "minimum": 0 },
        "peak_memory_gb": { "type": ["number", "null"], "minimum": 0 },
        "usd_per_item": { "type": ["number", "null"], "minimum": 0 },
        "credit_pool": {
          "description": "Which metered pool this spends, matching ProblemSpec.budget.credit_pools. Null means free tier.",
          "type": ["string", "null"]
        },
        "requires_network": { "type": ["boolean", "null"] },
        "measured": {
          "description": "True only if someone timed it. False means the number is a claim from a source.",
          "type": "boolean"
        },
        "measurement_basis": {
          "description": "What one 'item' is, and on what input size. 'per ligand, 300-residue receptor, 5 seeds' is usable; 'per run' is not.",
          "type": ["string", "null"]
        },
        "cost_notes": { "type": ["string", "null"] }
      }
    },

    "licence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["code_spdx", "weights_licence", "commercial_use", "weights_available", "api_only", "notes"],
      "properties": {
        "code_spdx": { "type": ["string", "null"] },
        "weights_licence": {
          "description": "Often different from the code licence, and often the blocking one.",
          "type": ["string", "null"]
        },
        "commercial_use": { "type": "string", "enum": ["yes", "no", "restricted", "unknown"] },
        "weights_available": { "type": ["boolean", "null"] },
        "api_only": { "type": ["boolean", "null"] },
        "notes": { "type": ["string", "null"] }
      }
    },

    "maturity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["level", "first_public", "last_activity", "independent_evaluations", "adoption_signal"],
      "properties": {
        "level": {
          "type": "string",
          "enum": [
            "announced_only",
            "published_no_independent_eval",
            "independently_benchmarked",
            "community_default",
            "superseded",
            "abandoned"
          ]
        },
        "first_public": { "type": ["string", "null"] },
        "last_activity": {
          "description": "Last commit, release, or paper revision. A dead repo is a cost.",
          "type": ["string", "null"]
        },
        "independent_evaluations": {
          "description": "Count of evaluations by people who are not the authors. Zero is the interesting answer.",
          "type": ["integer", "null"],
          "minimum": 0
        },
        "adoption_signal": {
          "description": "Concrete evidence of use, e.g. 'used by 3 of 12 CASP16 groups', 'GitHub 4k stars but 60 open issues'. Prose, cited in used_by.",
          "type": ["string", "null"]
        }
      }
    },

    "failure_modes": {
      "description": "Emit these as FindingKind.NEGATIVE or RISK and Predicate.FAILS_ON edges. An empty array on a mature method means you did not look.",
      "type": "array",
      "items": { "$ref": "#/$defs/failure_mode" }
    },

    "alternative_to": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["node_id", "relation", "note"],
        "properties": {
          "node_id": { "type": "string", "pattern": "^method:[a-z0-9][a-z0-9._+-]*$" },
          "relation": {
            "type": "string",
            "enum": ["drop_in", "partial_overlap", "different_tradeoff", "strict_upgrade", "strict_downgrade"]
          },
          "note": { "type": ["string", "null"] }
        }
      }
    },

    "used_by": {
      "description": "Who actually runs it. 'Published' and 'used' are different facts and the skill requires both.",
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["who", "context", "evidence", "note"],
        "properties": {
          "who": { "type": "string" },
          "context": {
            "type": "string",
            "enum": ["production", "competition_entry", "published_study", "benchmark_only", "tutorial_only", "unknown"]
          },
          "evidence": { "$ref": "#/$defs/evidence" },
          "note": { "type": ["string", "null"] }
        }
      }
    },

    "citations": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/evidence" }
    },

    "scout": {
      "type": "object",
      "additionalProperties": false,
      "required": ["modality", "queries", "scouted_utc", "agent", "confidence"],
      "properties": {
        "modality": {
          "description": "Which evidence modality this card came out of. See reference/evidence-modalities.md.",
          "type": "string",
          "enum": [
            "peer_reviewed", "preprint", "challenge_postmortem", "code_and_issues",
            "patent", "practitioner_talk", "benchmark_paper", "our_own_measurement"
          ]
        },
        "queries": {
          "description": "Verbatim query strings, so the pass is reproducible and diffable.",
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" }
        },
        "scouted_utc": { "type": "string" },
        "agent": { "type": ["string", "null"] },
        "confidence": {
          "description": "Confidence in the card as a whole, using reagent.contracts.report.Confidence.",
          "type": "string",
          "enum": ["established", "supported", "tentative", "speculative"]
        }
      }
    },

    "verdict": {
      "type": "object",
      "additionalProperties": false,
      "required": ["candidate", "rationale", "blocking_reason"],
      "properties": {
        "candidate": {
          "description": "Could this team run this method on this problem within budget? Not 'is it good'.",
          "type": "boolean"
        },
        "rationale": { "type": "string", "minLength": 15 },
        "blocking_reason": {
          "description": "Required when candidate is false. Null only when candidate is true.",
          "type": ["string", "null"]
        }
      }
    },

    "open_questions": {
      "description": "What you could not resolve. These flow to ModelReport.open_questions and then to cross-domain-analogy.",
      "type": "array",
      "items": { "type": "string" }
    },

    "notes": { "type": ["string", "null"] }
  },

  "$defs": {
    "io_item": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "format", "required", "note"],
      "properties": {
        "name": { "type": "string" },
        "format": {
          "description": "Concrete format, not a category. 'PDB with CONECT records' beats 'structure'.",
          "type": "string"
        },
        "required": { "type": "boolean" },
        "note": { "type": ["string", "null"] }
      }
    },

    "performance_claim": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "metric", "value", "direction", "eval_set", "eval_set_size",
        "subpopulation", "protocol", "spread", "reported_by", "source", "comparable_to"
      ],
      "properties": {
        "metric": {
          "description": "Exact metric name and implementation, e.g. 'LDDT-PLI (OpenStructure ligand_scoring)'.",
          "type": "string",
          "minLength": 3
        },
        "value": { "type": ["number", "string"] },
        "direction": { "type": "string", "enum": ["maximize", "minimize"] },
        "eval_set": {
          "description": "REQUIRED and non-nullable. Name the set, its composition, and the split. 'PoseBusters' is not enough; '428 PoseBusters-V1 complexes, no template filter' is.",
          "type": "string",
          "minLength": 15
        },
        "eval_set_size": { "type": ["integer", "null"], "minimum": 1 },
        "subpopulation": {
          "description": "If the number is for a slice, name the slice and its definition. Aggregate numbers hide sign-flipping priors.",
          "type": ["string", "null"]
        },
        "protocol": {
          "type": "object",
          "additionalProperties": false,
          "required": ["templates_allowed", "msa", "n_samples", "site_definition", "ground_truth_leakage_risk", "other"],
          "properties": {
            "templates_allowed": { "type": ["boolean", "null"] },
            "msa": { "type": ["string", "null"] },
            "n_samples": {
              "description": "Seeds or samples per item. A best-of-N number is not a best-of-1 number.",
              "type": ["integer", "null"],
              "minimum": 1
            },
            "site_definition": {
              "description": "How the binding site / pocket / region of interest was defined, or null if blind.",
              "type": ["string", "null"]
            },
            "ground_truth_leakage_risk": {
              "description": "Anything that could have leaked the answer: training cutoff after the test structures were deposited, holo receptor supplied, pocket from the answer.",
              "type": ["string", "null"]
            },
            "other": { "type": ["string", "null"] }
          }
        },
        "spread": {
          "description": "Confidence interval, standard deviation, bootstrap spread, or seed-to-seed range. Null means the source reported a point estimate only, which is a weakness worth recording.",
          "type": ["string", "null"]
        },
        "reported_by": {
          "type": "string",
          "enum": ["method_authors", "independent_benchmark", "challenge_organizer", "third_party_blog", "us"]
        },
        "source": { "$ref": "#/$defs/evidence" },
        "comparable_to": {
          "description": "Ids of other claims measured on the SAME eval_set and protocol. Only these may be subtracted from each other.",
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },

    "failure_mode": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "symptom", "mechanism", "severity", "affected_subpopulation", "mitigation", "residual_risk", "catalogue_ref", "evidence"],
      "properties": {
        "name": { "type": "string" },
        "symptom": {
          "description": "What you OBSERVE when it happens, not what is wrong. Someone must be able to detect it.",
          "type": "string",
          "minLength": 15
        },
        "mechanism": { "type": ["string", "null"] },
        "severity": { "type": "string", "enum": ["fatal", "major", "minor", "unknown"] },
        "affected_subpopulation": { "type": ["string", "null"] },
        "mitigation": { "type": ["string", "null"] },
        "residual_risk": { "type": ["string", "null"] },
        "catalogue_ref": {
          "description": "Entry id in reference/failure-mode-catalogue.md, e.g. 'B2'. Null if this is a new mode; then add it to the catalogue.",
          "type": ["string", "null"]
        },
        "evidence": { "$ref": "#/$defs/evidence" }
      }
    },

    "evidence": {
      "description": "Converts directly into reagent.contracts.report.Evidence.",
      "type": "object",
      "additionalProperties": false,
      "required": ["source_type", "locator", "title", "excerpt", "year", "source_domain"],
      "properties": {
        "source_type": {
          "type": "string",
          "enum": [
            "paper", "preprint", "patent", "clinical_trial", "regulatory_doc", "thesis",
            "structure", "database", "dataset", "code_repo", "competition",
            "blog", "social", "documentation", "talk",
            "computation", "benchmark", "cross_domain_analogy", "expert_prior"
          ]
        },
        "locator": {
          "description": "Resolvable: DOI, PMID, PMC id with line anchor (pmc:PMC123#L45-L52), GitHub issue URL, patent number, leaderboard URL, or repo-relative path for computation.",
          "type": "string",
          "minLength": 3
        },
        "title": { "type": ["string", "null"] },
        "excerpt": {
          "description": "Verbatim span. Do not paraphrase here.",
          "type": ["string", "null"]
        },
        "year": { "type": ["integer", "null"] },
        "source_domain": {
          "description": "Required when source_type is cross_domain_analogy, null otherwise.",
          "type": ["string", "null"]
        }
      }
    }
  }
}
```

## Worked example: a selection-position method

This is the cross-model selector from the reference case study, written as the
card a scout should have produced. It is chosen deliberately: it is a
**selection** method rather than a model, its cost fields are honestly null, and
one of its performance claims is a subpopulation number rather than an aggregate.

```json
{
  "card_version": "1.0.0",
  "node_id": "method:zscored-native-confidence-argmax",
  "name": "Cross-model z-scored native-confidence argmax",
  "version": "case-study lineage 'prot_rescue8', iteration 7",
  "aliases": ["z-hybrid selector", "4-model z-hybrid confidence selector"],
  "one_line": "Rank each co-folder's samples by that model's own confidence head, z-score each model's per-item best scores across the whole test set, then pick the model with the highest z per item.",
  "pipeline_position": {
    "step": "ranking_selection",
    "step_node_id": "step:ranking-selection",
    "role": "Consumes a pool of poses from several structure predictors, each carrying its native confidence output, and emits exactly one pose per test item. Adds no new conformations.",
    "is_terminal": false
  },
  "io": {
    "inputs": [
      {
        "name": "pose pool",
        "format": "one PDB or mmCIF per (model, seed, item), plus the per-sample native confidence scalar",
        "required": true,
        "note": "Case study pool: AlphaFold3 (4-10 seeds), Boltz-2.1 (5-10), OpenFold3 (20), Chai-1 (5), Protenix-v2 (25), ESMFold2 (25 per MSA mode, 4 modes)."
      },
      {
        "name": "native confidence key per model",
        "format": "string naming the field, sign-corrected so higher is better",
        "required": true,
        "note": "Case study mapping: AF3 iptm; Boltz-2 negated complex_ipde; OpenFold3 negated mean PAE over the pocket-ligand block; Chai-1 iptm."
      }
    ],
    "outputs": [
      { "name": "selected pose per item", "format": "one PDB per item", "required": true, "note": null },
      { "name": "per-item z table", "format": "CSV of item by model z-scores", "required": false, "note": "Needed downstream to identify the low-confidence tail for rescue." }
    ],
    "hard_requirements": [
      "At least two models with independently-trained confidence heads, since the method compares across models",
      "Enough items to z-score over; the case study used all 184 test items as the normalisation population",
      "Each model's confidence must be exported per sample, not only per run"
    ]
  },
  "performance": [
    {
      "metric": "LDDT-PLI (OpenStructure ligand_scoring, bootstrap-averaged over 1000 resamples)",
      "value": 0.5472,
      "direction": "maximize",
      "eval_set": "OpenADMET PXR blind test set: 184 PXR-LBD plus small-molecule pairs, comprising 76 PanDDA fragment soaks and 108 drug-like analogs, scored server-side on the live half of the split",
      "eval_set_size": 184,
      "subpopulation": null,
      "protocol": {
        "templates_allowed": null,
        "msa": "per-model default, plus 4 MSA modes for the ESMFold2 arm",
        "n_samples": null,
        "site_definition": "blind, no pocket supplied",
        "ground_truth_leakage_risk": "none for the selector itself; the underlying co-folders have unknown training cutoffs relative to the PXR depositions",
        "other": "Compared against 0.4996 for the same pool selected without cross-model z-scoring. The two numbers share this eval set and are therefore subtractable: the z-scoring step is worth +0.0476."
      },
      "spread": "not reported per submission; the organiser's bootstrap averaging is over 1000 resamples",
      "reported_by": "challenge_organizer",
      "source": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#the-winning-method",
        "title": "Case study: the rank-2 OpenADMET PXR entry, reverse-engineered",
        "excerpt": "This is the core trick and it took 0.4996 to 0.5472.",
        "year": null,
        "source_domain": null
      },
      "comparable_to": ["claim:pool-no-zscore-0.4996", "claim:prot-rescue8-0.5640"]
    },
    {
      "metric": "LDDT-PLI (OpenStructure ligand_scoring)",
      "value": 0.5640,
      "direction": "maximize",
      "eval_set": "same OpenADMET PXR blind test set, 184 pairs, live half",
      "eval_set_size": 184,
      "subpopulation": null,
      "protocol": {
        "templates_allowed": null,
        "msa": "as above",
        "n_samples": null,
        "site_definition": "blind",
        "ground_truth_leakage_risk": "none for the selector",
        "other": "This is the selector plus failure-tail rescue: the 8 lowest-confidence items overwritten with Protenix-v2 poses. Swapping 4 gave 0.5578, 8 gave 0.5640, 12 gave 0.5629, 20 gave 0.5587, so the rescue count is a tuned hyperparameter with an interior optimum."
      },
      "spread": null,
      "reported_by": "challenge_organizer",
      "source": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#final-standing",
        "title": "Case study: final standing, rank 2 of about 50",
        "excerpt": "Best score 0.5640 LDDT-PLI; best rank 2 / ~50",
        "year": null,
        "source_domain": null
      },
      "comparable_to": ["claim:pool-no-zscore-0.4996"]
    }
  ],
  "cost": {
    "hardware": "CPU only for the selector itself; the pool it consumes required GPU inference across six predictors",
    "wall_seconds_per_item": null,
    "throughput_per_hour": null,
    "peak_memory_gb": null,
    "usd_per_item": null,
    "credit_pool": null,
    "requires_network": false,
    "measured": false,
    "measurement_basis": null,
    "cost_notes": "The selector is arithmetic over a scores table and its own cost is negligible, but it is not free: it is only defined on top of a multi-model pool, and that pool is the real expenditure. Cost the pool, not the argmax. Timings were not recorded in the source; measure this yourself before quoting one."
  },
  "licence": {
    "code_spdx": null,
    "weights_licence": null,
    "commercial_use": "unknown",
    "weights_available": null,
    "api_only": false,
    "notes": "The method is ~30 lines of arithmetic and is not meaningfully licensable; the licence question transfers entirely to the co-folders in the pool, each of which must be carded separately. No LICENSE file is recorded for the source repo, so treat the reference implementation as unlicensed until confirmed."
  },
  "maturity": {
    "level": "published_no_independent_eval",
    "first_public": null,
    "last_activity": null,
    "independent_evaluations": 0,
    "adoption_signal": "One competition entry, rank 2 of about 50. No independent reproduction is recorded, which is the main reason this card is 'supported' and not 'established'."
  },
  "failure_modes": [
    {
      "name": "Confidence heads are miscalibrated on out-of-distribution items",
      "symptom": "The selector's chosen pose is confidently wrong on a small subset, and the per-item z-score does not correlate with realised accuracy on that subset.",
      "mechanism": "A confidence head is trained to predict its own model's error distribution on its own training distribution. On items far outside it, the head reports high confidence for the wrong reason.",
      "severity": "major",
      "affected_subpopulation": "In the case study, the PanDDA fragments: Morgan-r2 Tanimoto below 0.3 to every known PXR holo ligand, often engaging zero canonical pocket anchors.",
      "mitigation": "Do not try to fix the score. Detect the low-confidence tail and overwrite it with a different model's pose. Swapping the 8 lowest-confidence items moved the score from 0.5472 to 0.5640; one rescued item went from 0.123 to 0.919.",
      "residual_risk": "The rescue count is tuned without ground truth. Over-swapping degrades: 20 swaps scored 0.5587, below the 8-swap 0.5640.",
      "catalogue_ref": "C5",
      "evidence": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#the-winning-method",
        "title": "Rescue-count sweep",
        "excerpt": "One rescue went 0.123 to 0.919. Over-swapping hurts - the tail is real but small.",
        "year": null,
        "source_domain": null
      }
    },
    {
      "name": "Cannot reach hybrid solutions that exist in the pool",
      "symptom": "The pool oracle improves when you add recombined candidates, but the realised score does not move.",
      "mechanism": "An argmax over whole poses can only return a pose that some model produced. Any candidate whose value comes from combining parts of two poses is invisible to it.",
      "severity": "major",
      "affected_subpopulation": null,
      "mitigation": "None known within this method. In the case study a genetic anchor-and-tail crossover raised the oracle but no selector could find the hybrid.",
      "residual_risk": "Widening the pool with recombination is wasted effort unless the selector is redesigned first. Measure the oracle and the realised score together, never the oracle alone.",
      "catalogue_ref": "B4",
      "evidence": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#what-was-refuted-and-how",
        "title": "Refuted: genetic anchor+tail crossover",
        "excerpt": "oracle improved, but no selector could find the hybrid. A pure selection-wall casualty.",
        "year": null,
        "source_domain": null
      }
    }
  ],
  "alternative_to": [
    {
      "node_id": "method:consensus-medoid-pose-selection",
      "relation": "different_tradeoff",
      "note": "Consensus, medoid, Borda count and reciprocal-rank fusion were all tried on the same pool and all regressed against this method. They fail for a structural reason: agreeing models share correlated errors, so voting concentrates on the shared error mode."
    },
    {
      "node_id": "method:learned-pose-rescorer-lambdamart",
      "relation": "different_tradeoff",
      "note": "The learned alternative scored 0.4762 and rank 32, the worst submission of that project, because it had only 35 to 53 labelled holo structures to train on."
    }
  ],
  "used_by": [
    {
      "who": "The rank-2 entry in the OpenADMET PXR blind structure challenge",
      "context": "competition_entry",
      "evidence": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md",
        "title": "Case study: the rank-2 OpenADMET PXR entry",
        "excerpt": null,
        "year": null,
        "source_domain": null
      },
      "note": "One documented user. Treat single-entry adoption as a warning, not an endorsement."
    }
  ],
  "citations": [
    {
      "source_type": "documentation",
      "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md",
      "title": "Case study: the rank-2 OpenADMET PXR entry, reverse-engineered",
      "excerpt": null,
      "year": null,
      "source_domain": null
    }
  ],
  "scout": {
    "modality": "challenge_postmortem",
    "queries": [
      "OpenADMET PXR structure prediction challenge results write-up",
      "cross-model confidence z-score pose selection co-folding"
    ],
    "scouted_utc": "2026-08-15T00:00:00Z",
    "agent": "stage0-scout-postmortems",
    "confidence": "supported"
  },
  "verdict": {
    "candidate": true,
    "rationale": "Costs nothing beyond the pool we would build anyway, requires no labels, and has a measured +0.0476 on a blind 184-item set. It is the default selector to beat rather than an idea to test.",
    "blocking_reason": null
  },
  "open_questions": [
    "Does z-scoring across items still work when the test set is small, since the normalisation population is the test set itself?",
    "Is there a selector that can reach recombined candidates without ground-truth labels?"
  ],
  "notes": "Two locator caveats in this example, both deliberate. First, the sources point at our reverse-engineered case study rather than at the live leaderboard, because no leaderboard URL is recorded; a production card must cite the leaderboard directly. Second, the case study reports the pool oracle in angstroms of RMSD while the leaderboard reports LDDT-PLI, so those two numbers cannot be subtracted. See reference/generation-vs-selection.md."
}
```

### A compact second example: a refuted method

Cards for methods that failed are the highest-value output of this stage, and
they are short, because a refuted method needs no cost model. Note that
`performance` is populated (a bad number is still a number with an eval set) and
`verdict.candidate` is false.

```json
{
  "card_version": "1.0.0",
  "node_id": "method:learned-pose-rescorer-lambdamart",
  "name": "XGBoost LambdaMART learned pose re-scorer",
  "version": "37-feature variant",
  "aliases": ["learned pose scorer", "supervised rescoring"],
  "one_line": "Learns a ranking function over pose features with gradient-boosted trees and a LambdaMART objective, then re-ranks the candidate pool with it instead of using native model confidence.",
  "pipeline_position": {
    "step": "ranking_selection",
    "step_node_id": "step:ranking-selection",
    "role": "Replaces the native-confidence selector with a supervised model trained on locally-available ground-truth structures.",
    "is_terminal": false
  },
  "io": {
    "inputs": [
      { "name": "pose pool with features", "format": "37 numeric features per pose", "required": true, "note": null },
      { "name": "labelled training structures", "format": "experimental holo complexes with the same receptor", "required": true, "note": "This is the binding constraint, not the features." }
    ],
    "outputs": [
      { "name": "re-ranked pool", "format": "score per pose", "required": true, "note": null }
    ],
    "hard_requirements": [
      "Enough labelled ground-truth items to fit a 37-feature ranker. 35 to 53 was demonstrably far too few."
    ]
  },
  "performance": [
    {
      "metric": "LDDT-PLI (OpenStructure ligand_scoring)",
      "value": 0.4762,
      "direction": "maximize",
      "eval_set": "OpenADMET PXR blind test set, 184 pairs, live half, same pool as the z-score selector",
      "eval_set_size": 184,
      "subpopulation": null,
      "protocol": {
        "templates_allowed": null,
        "msa": "as the underlying pool",
        "n_samples": null,
        "site_definition": "blind",
        "ground_truth_leakage_risk": "none; the risk ran the other way, too little ground truth",
        "other": "Rank 32 of about 50, and the worst submission that project made. Trained on 35 to 53 holo structures."
      },
      "spread": null,
      "reported_by": "challenge_organizer",
      "source": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#what-was-refuted-and-how",
        "title": "Refuted approaches",
        "excerpt": "Learned pose scorer (XGBoost LambdaMART, 37 features) - scored 0.4762 / rank 32, the project's worst submission. Trained on 35-53 holos: far too few.",
        "year": null,
        "source_domain": null
      },
      "comparable_to": ["claim:pool-no-zscore-0.4996", "claim:prot-rescue8-0.5640"]
    }
  ],
  "cost": {
    "hardware": "CPU, minutes",
    "wall_seconds_per_item": null,
    "throughput_per_hour": null,
    "peak_memory_gb": null,
    "usd_per_item": 0,
    "credit_pool": null,
    "requires_network": false,
    "measured": false,
    "measurement_basis": null,
    "cost_notes": "Compute cost is irrelevant here; the cost that mattered was a submission slot."
  },
  "licence": {
    "code_spdx": "Apache-2.0",
    "weights_licence": null,
    "commercial_use": "yes",
    "weights_available": null,
    "api_only": false,
    "notes": "XGBoost itself is permissive; the trained ranker is ours."
  },
  "maturity": {
    "level": "independently_benchmarked",
    "first_public": null,
    "last_activity": null,
    "independent_evaluations": 1,
    "adoption_signal": "Widely used in other ranking domains, and refuted here on this task at this label count. Both facts are true and the second one governs."
  },
  "failure_modes": [
    {
      "name": "Supervised selector starved of labels",
      "symptom": "Local validation looks competitive while the blind score drops well below the unlearned baseline.",
      "mechanism": "A 37-parameter-family ranker fitted to a few dozen items memorises the validation set. There is no regularisation strength that recovers a signal that was never resolvable at that sample size.",
      "severity": "fatal",
      "affected_subpopulation": null,
      "mitigation": "Do not train a selector until you can count labels in the hundreds. Until then use the unlearned baseline, which needs zero.",
      "residual_risk": "The temptation returns every time the validation set grows a little. Expanding 35 to 53 was not enough.",
      "catalogue_ref": "A3",
      "evidence": {
        "source_type": "competition",
        "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#what-was-refuted-and-how",
        "title": "Refuted approaches",
        "excerpt": "Trained on 35-53 holos: far too few.",
        "year": null,
        "source_domain": null
      }
    }
  ],
  "alternative_to": [
    { "node_id": "method:zscored-native-confidence-argmax", "relation": "strict_downgrade", "note": "Same pool, same eval set, 0.4762 against 0.5640." }
  ],
  "used_by": [],
  "citations": [
    {
      "source_type": "documentation",
      "locator": ".claude/skills/ai-scientist/reference/pxr-case-study.md#what-was-refuted-and-how",
      "title": "Case study: what was refuted, and how",
      "excerpt": null,
      "year": null,
      "source_domain": null
    }
  ],
  "scout": {
    "modality": "challenge_postmortem",
    "queries": ["learned rescoring function pose selection small training set negative result"],
    "scouted_utc": "2026-08-15T00:00:00Z",
    "agent": "stage0-scout-postmortems",
    "confidence": "supported"
  },
  "verdict": {
    "candidate": false,
    "rationale": "Refuted on this problem class at the label count available. Keep the card so nobody proposes it again in iteration 4.",
    "blocking_reason": "Requires hundreds of labelled ground-truth items; we have tens."
  },
  "open_questions": [
    "At what label count does a learned selector overtake the z-scored native-confidence baseline? Nobody has published the crossover."
  ],
  "notes": null
}
```

## The fields, one at a time

**`node_id`, `name`, `version`, `aliases`.** The id is what makes two scouts
working different modalities collapse onto one graph node instead of two, so it
follows the `kg.Node` convention of a namespaced, resolvable key. Version is not
bureaucracy: "Boltz" and "Boltz-2.1" have different performance and different
licences, and a card that omits the version cannot be compared to anything later.
`aliases` catches the common case where a preprint, a repo, and a leaderboard use
three different names for one thing.

**`one_line`.** Mechanistic, not promotional. The test is whether a reader can
predict what the method will fail at from the sentence alone. "Diffusion-based
all-atom co-folding conditioned on an MSA" passes. "State-of-the-art structure
prediction" fails.

**`pipeline_position`.** This is the field that turns a reading list into a
decision tree. The `step` enum is the set of slots a prediction pipeline has, and
it is deliberately wider than the modelling steps: `data_curation`,
`submission_packaging` and `evaluation` are in there because real leaderboards
have been decided in those slots. `is_terminal` distinguishes a method that can
produce a submission by itself from one that only makes sense inside a larger
pipeline; the second kind needs its dependencies costed too, which is why the
selector example above has `is_terminal: false` and a `cost_notes` that redirects
you to the pool.

**`io`.** `hard_requirements` is the field that kills candidates cheaply. A
method that requires a holo template is not a candidate when no close-homolog
holo structure exists. A method that requires hundreds of labelled examples is
not a candidate when you have 53. Write these before writing the performance
numbers, because half the time the requirement disqualifies the method and you
can stop.

**`performance`.** An array, because one method has many numbers, and each is
tied to its own evaluation set and protocol. `comparable_to` is the discipline
mechanism: two claims may only be subtracted if they name each other there. In
the worked example, 0.4996 and 0.5472 are comparable because they are the same
pool and the same 184 items, so their difference of 0.0476 is a real measurement
of the z-scoring step. The pool oracle of roughly 1.08 Å median RMSD is *not*
comparable to either, because it is a different metric in different units, and
that is precisely the kind of subtraction people do by accident.

`protocol.n_samples` deserves special attention. A number produced by taking the
best of 25 seeds is not the same claim as a single-shot number, and papers
routinely report the first while readers hear the second. The case study pool
ranged from 4 seeds for one predictor to 25 for another, which alone changes what
a per-model score means.

`protocol.ground_truth_leakage_risk` is where you record the awkward question. If
a model's training data was assembled after the test structures were deposited,
its benchmark number is not a blind number, and no amount of good faith fixes
that. Write the risk down even when you cannot quantify it.

**`cost`.** Hardware, wall-clock, memory, money, and which metered credit pool it
spends, plus the `measured` flag that separates a timing someone took from a
timing someone claimed. `measurement_basis` exists because "30 seconds per run"
is uninterpretable: per what input size, with how many seeds, including or
excluding MSA generation? Stage 0 is a free-tier stage and must not spend Boltz,
Modal or Tamarind credits, so most cost fields at this stage are claims from
sources with `measured: false`. That is fine and honest. What is not fine is
promoting a method to candidate on an uncosted claim.

**`licence`.** Split into code and weights because they differ constantly and the
weights licence is usually the blocking one. `commercial_use` is an enum
including `restricted` and `unknown` rather than a boolean, because
non-commercial-research-only clauses are the single most common reason a
benchmark-winning method cannot be used.

**`maturity`.** `independent_evaluations: 0` is the most informative value this
field takes, and the skill's anti-pattern list names the failure directly:
chasing the newest model with no independent evaluation is a risk, not an
advantage. `last_activity` catches the abandoned repository, whose real cost is
the week you spend making it run.

**`failure_modes`.** Each needs an observable symptom, because a failure mode you
cannot detect is not actionable. `catalogue_ref` links to
`reference/failure-mode-catalogue.md`, and a null there is an instruction: you
found a mode the catalogue does not have, so add it. An empty `failure_modes`
array on a widely-used method means the scout searched only the method paper,
which does not print them.

**`alternative_to`.** Populates `Predicate.ALTERNATIVE_TO` and is what lets a
downstream reader ask "what else occupies this slot" rather than reading the
whole landscape. The `relation` enum distinguishes a drop-in swap from a
different trade-off, since only the first can be tested by substitution.

**`used_by`.** The skill's first guard rail is to separate "published" from
"used". A method that wins benchmarks and that nobody runs is telling you
something about cost or fragility, and this field is where you record which of
the two you found. `context: "benchmark_only"` and `context: "tutorial_only"` are
the diagnostic values.

**`citations`.** At least one, always. An uncited method node is a bug, and the
report validator will refuse an `OBSERVATION`, `BENCHMARK`, `NEGATIVE` or `PRIOR`
finding with no `Evidence` anyway. Line-anchored locators
(`pmc:PMC12690452#L45-L52`) are strongly preferred, because the next agent can
check the claim without re-reading the paper.

**`scout`.** Modality plus the verbatim queries plus a whole-card confidence
level. The confidence value has to respect the project's grounding rules: a card
whose citations are all grey sources such as blogs, forum posts, issue trackers
or competition write-ups may be `supported` but may not be `established`, and
`established` needs at least two independent grounded sources with at least one
reviewed or structured-database source among them.

**`verdict`.** The card's one opinion, and it answers "could we run this", not
"is this good". Splitting the opinion from the facts is what lets a later reader
disagree with the verdict without re-scouting the method.

**`open_questions`.** These flow into `ModelReport.open_questions`, then into
`cross-domain-analogy` as its input. An unanswered question in-field is exactly
where an out-of-field mechanism is worth borrowing, and the analogy engine
free-associates without them.

## Why performance without an eval set is rejected

Not as a matter of rigour. Because the number changes by more than the entire
competitive margin depending on what it was measured over, so a bare number is
not a weak fact but a random one.

Three measurements from the reference case study make this concrete.

**The same submission scores differently by subpopulation.** Across the submitted
co-folder models, scores were about 0.46 on the drug-like half of the test set
and about 0.55 to 0.57 on the fragment half. That is a spread of roughly 0.09 to
0.11 within one submission, driven entirely by which items you average over. Now
put the competitive context next to it: the gap between rank 2 (0.5640) and the
winner (0.5725) was 0.0085. The subpopulation ambiguity is more than ten times
the margin that decided the standings. A card reporting "0.55" without saying
which half of the test set it covers has told you nothing you can act on, and
worse, it has told you something you will act on wrongly.

**Local ground truth and the real metric were not monotonic.** On a 35-structure
local validation set, every method clustered within 0.05 Å, which is the noise
floor of that set, while the leaderboard spanned a range five times wider. Two
numbers from those two sources are not two measurements of the same quantity, and
subtracting them produces a conclusion with no content. This is why `eval_set`
must name the set and its composition rather than a family: "PoseBusters" is not
an eval set, "428 PoseBusters-V1 complexes, no template filter, single seed" is.

**Changing the eval set changed the ranking of methods.** Expanding local
validation from 35 to 53 holo structures moved every method up by about 0.020 on
the local proxy, except one, which gained 0.0015 and fell from first place to
last. Same methods, same poses, different eval set, inverted ranking. If the
`eval_set` field is missing you cannot detect that this has happened to you, and
the signature of an overfit is exactly this failure to improve when the task gets
easier.

The general shape: a performance number is a function of the method *and* the
evaluation protocol, and in this problem class the protocol term is frequently
larger than the method term. Dropping it does not make the number approximate. It
makes it a different number.

The same reasoning applies outside structure prediction, which is why the field
is required for every domain the project supports rather than only for
structural biology. An ADMET regression's Spearman correlation depends on whether
the split was random or scaffold-based, and the two differ by far more than
competing models differ from each other. A DNA-encoded-library hit rate depends
on whether the enrichment threshold was set before or after seeing the data. A
binder-design success rate depends on whether "success" means a measurable
binding signal or a specified affinity. In every case the protocol term dominates
and the bare number is unusable.

The mechanical consequence, and the reason the schema rather than a guideline
enforces it: `Metric.eval_set` in `src/reagent/contracts/problem.py` carries the
comment "A metric without this is uncomparable", and the Stage 0 handoff feeds
`must_beat` baselines to Stage 3. A baseline with no eval set propagates a
meaningless target through three more stages, each of which will optimise against
it faithfully.

## Rejection checklist

Reject a returned card, and send the scout back, when any of these hold.

| Condition | Why it is fatal |
|---|---|
| A `performance` entry with a short, generic, or family-level `eval_set` | The number cannot be compared to anything, including the baselines this stage exists to fix |
| `comparable_to` empty while the card's prose subtracts two numbers | An uncomparable subtraction, which is the most common false claim in a scouting pass |
| `verdict.candidate: true` with `cost.hardware` null and no throughput | Violates "do not rank methods you have not costed" |
| Empty `failure_modes` on a method with `maturity.level` of `community_default` | A widely-used method has known failure modes; an empty array means only the method paper was read |
| Empty `citations` | An uncited method node is a bug, and the report validator rejects the derived finding |
| Empty `scout.queries` | The pass is not reproducible and cannot be diffed against the next one |
| `scout.confidence: "established"` with only grey citations, or fewer than two distinct grounded locators | Breaks the `Finding` grounding rule and will fail report validation downstream |
| Cost numbers with `measured: true` and no `measurement_basis` | An uninterpretable timing, which will be trusted and then be wrong |

## From cards to the graph and the report

One card produces, mechanically:

- One `Method` node at `node_id`, with the card's `one_line`, `version` and
  `maturity` in `attrs`.
- One `Predicate.USED_IN` edge from the method to `pipeline_position.step_node_id`.
- One `Predicate.EVALUATED_ON` edge per `performance` entry, carrying `{metric,
  value, eval_set, n, protocol}` in `attrs`. The eval set travels on the edge, so
  the graph cannot hold a bare number either.
- One `Predicate.FAILS_ON` edge per `failure_modes` entry.
- One `Predicate.ALTERNATIVE_TO` edge per `alternative_to` entry.
- One `Predicate.SUPPORTED_BY` edge per `citations` entry, to a `Paper` node.
- `Predicate.OUTPERFORMS` edges only between claims that name each other in
  `comparable_to`, with `{metric, delta, eval_set}` in `attrs`.

And in the `ModelReport`: `performance` entries become `FindingKind.BENCHMARK`,
`failure_modes` become `FindingKind.NEGATIVE` or `FindingKind.RISK`, `verdict`
plus `pipeline_position` become `FindingKind.DESIGN_CHOICE`, and anything in the
`io.hard_requirements` or submission-mechanics category becomes
`FindingKind.CONSTRAINT`.

One convention note. `reagent.contracts.kg.Node` documents id namespaces for
`Protein`, `Structure`, `Pocket`, `Compound`, `Motif`, `Paper`, `Family`,
`Method`, `Analogy` and `Domain`, but not for `PipelineStep`. This document fixes
`step:<slug>` and the schema enforces it by pattern. If that convention is added
to `kg.py` later, the pattern here must be updated to match.
