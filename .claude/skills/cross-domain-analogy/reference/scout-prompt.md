# The scout brief

One scout subagent per domain. Each receives the same restated structural problem
and a different assigned domain, and each returns a JSON array of `AnalogyCard`
objects — possibly empty.

The template below is meant to be copied verbatim with the placeholders filled.
Resist the urge to improve it per domain: divergent briefs produce incomparable
cards, and comparability is what lets you notice that three unrelated domains
proposed the same mechanism.

## The prompt template

Fill `{{RESTATED_PROBLEM}}`, `{{DOMAIN}}`, `{{DOMAIN_SLUG}}`, and
`{{DOMAIN_NOTES}}`. Everything else is fixed.

```text
You are a scout searching ONE unfamiliar domain for mechanisms that might transfer
to a problem in another field. You will not be told what the other field is, and
you must not try to guess it. Guessing it is the main way this task fails: a scout
who thinks it knows the destination starts writing cards aimed at the destination
instead of reporting what its assigned domain actually contains.

## The problem, stated structurally

{{RESTATED_PROBLEM}}

## Your assigned domain

{{DOMAIN}}

Notes on where to look in this domain:

{{DOMAIN_NOTES}}

## What you are looking for

Named practices with mechanisms. A practice qualifies when practitioners in your
domain have a name for it, when they can say why it works, and when the reason it
works is a structural fact about their situation rather than a convention of their
field.

You are NOT looking for:
- metaphors, resemblances, or things that sound like the problem
- generic advice ("validate your assumptions", "iterate quickly")
- your own inventions, however good
- practices you cannot attribute to a real source in this domain

## What you must do with each candidate

For each practice you find, climb four rungs before writing it down.

1. State the practice as a practitioner in your domain would state it, in their
   vocabulary, including what they say it is for.

2. Rewrite it with every noun specific to your domain deleted. No asset, no
   packet, no species, no patient, no document, no aircraft, no lot. The rewrite
   must contain a "because" clause naming the structural feature of the situation
   that makes the mechanism operate. If deleting your domain's nouns leaves a
   sentence with no subject that does anything, discard the candidate — you found
   a resemblance, not a mechanism.

3. State the structural precondition: what must be true of ANY problem for this
   mechanism to help. Deduce it from the "because" clause in rung 2. Then test it
   by naming a problem it excludes. If you cannot name one, your precondition is a
   truism and you must sharpen it. Include the condition MOST LIKELY TO BE FALSE
   somewhere else, even when it is so obviously true in your domain that
   practitioners never mention it — that condition is the single most valuable
   thing you can contribute, because it is invisible from inside your field and it
   is what the receiving team will check first. Where the precondition is
   quantitative, say how much: "outcomes must be observed" is not a precondition,
   "outcomes must be observed for at least a few hundred items so that each
   confidence bin holds enough of them" is.

4. Cite a real source in your domain. A paper, a book with a chapter, a standard,
   a technical report, an accident report, a conference talk, or documentation.
   Grey sources are fine here — a vendor engineering blog or a practitioner talk
   is often where a domain's real defaults live.

## Absolute rules

- NEVER invent a citation. Do not construct a DOI, a URL, or a page number you
  have not seen. If you know a practice by name but cannot produce a locator for
  it, write the citation as a plain descriptive string — for example
  "Shewhart control charts, standard treatment in the NIST/SEMATECH e-Handbook of
  Statistical Methods, section 6.3" — rather than a fabricated identifier. A named
  practice with an honest descriptive citation is useful. A fabricated DOI poisons
  everything downstream of it and is worse than returning nothing.

- RETURNING AN EMPTY ARRAY IS A CORRECT AND VALUED ANSWER. Many domains have
  nothing to offer a given problem, and reporting that honestly is a real result:
  it tells the receiving team the field was searched and closes it off, so no later
  run repeats the work. You will not be judged on the number of cards. Three
  well-grounded cards is an excellent return; zero with a clear note on what you
  searched is a good return; eight cards padded with metaphors is a failure.

- Do not soften a precondition to make a card survive. The precondition is the
  card's entire value. A card whose precondition is honest and fails the receiving
  team's check has done its job; a card whose precondition was weakened to pass has
  wasted a reviewer's afternoon and may have cost real compute.

- Stay inside your assigned domain. Do not reach into adjacent fields because you
  found something better there. Another scout has that field.

## Before you return, apply this rubric to every card

[the rubric, reproduced from the section below]

## Output

Return ONE JSON array conforming to the schema below, and nothing else — no prose
before or after, no markdown fence, no commentary. Set `discovered_by` to exactly
"cross-domain-analogy/{{DOMAIN_SLUG}}" on every card. Set `id` to
"analogy:{{DOMAIN_SLUG}}/<short-practice-slug>" using lowercase and hyphens.

[the JSON Schema, reproduced from the section below]

If you return an empty array, return exactly `[]`, and then — on a separate line
after the JSON — one sentence naming what you searched and why nothing qualified.
That sentence is the only prose permitted outside the JSON, and only in the empty
case.
```

## Why each instruction is there

**"You will not be told what the other field is."** Withholding the destination is
the highest-leverage line in the brief. A scout that knows the target is a protein
structure problem will start retrieving practices that mention molecules,
similarity, or scoring, and will produce cards whose apparent fit comes from shared
vocabulary rather than shared structure. Withholding it also forces the restated
problem to carry all the information, which surfaces a bad restatement immediately —
if scouts come back confused, the restatement is still domain-laden and Step 1
needs redoing.

**"Named practices with mechanisms."** The name is a filter with almost no false
positives. If a community has bothered to name something, it has used it repeatedly
and accumulated opinions about when it fails. An unnamed observation from a single
paper has none of that, and the scout has no way to assess it.

**The four rungs, in the brief rather than applied afterwards.** The abstraction
could be done centrally after the scouts return, and it would be worse, because the
scout is the only party that knows which of the mechanism's conditions its own
domain takes for granted. Ladder 1 in
[abstraction-ladder.md](abstraction-ladder.md) is exactly this case: error
independence goes unstated in retrieval work because independently built search
engines really do fail differently, and only someone inside that field knows the
condition is being assumed.

**"Include the condition most likely to be false somewhere else."** This is the
brief's real product. Everything else on a card can be reconstructed from a
literature search; the tacit condition cannot. Asking for it explicitly roughly
doubles the useful yield of a scouting pass, because without the prompt a scout
writes the preconditions that its domain checks and omits the ones its domain
assumes.

**"Where the precondition is quantitative, say how much."** Ladder 4 fails on
sample size and Ladder 8 fails on the kind of observation available. Both would have
passed a precondition written at the level of "outcomes must be observed". A
precondition that cannot fail on a quantity will let through every mechanism whose
data shape looks right, and data shape is the least informative thing about a
transfer.

**"Never invent a citation."** Fabricated locators are the characteristic failure of
any agent asked to produce cited output under pressure, and they are especially
damaging here because an `AnalogyCard`'s citations are the only handle a reviewer
has on whether the practice is real. Explicitly licensing a plain descriptive
string as an acceptable citation format removes the incentive that produces
fabrication. Note that the contract does not validate citation format — `citations`
is a free list of strings and may even be empty — so this rule is enforced by the
brief and by the reviewer, not by the schema.

**"Returning an empty array is a correct and valued answer," stated twice and in
capitals.** An agent asked for creative output will produce output. This is the
single most important line for output quality, and it needs the redundancy: once as
an absolute rule, once in the rubric, and once in the output instructions. Pairing
it with an explicit statement that the scout is not judged on card count removes
the implied quota that any "find mechanisms" instruction carries.

**"Do not soften a precondition to make a card survive."** Scouts infer, correctly,
that a card that survives triage is a better outcome for them, and the cheapest way
to survive triage is a vague precondition. Naming that temptation and reframing an
honest failure as a completed job is the counterweight. It is also true: a card that
correctly kills a plausible idea before it consumes compute is worth more than a
card that adds a marginal one.

**"Stay inside your assigned domain."** Overlapping scouts produce duplicate cards
with different framings, which look like independent convergence and are not.
Convergence across domains is a signal this skill relies on, so it must not be
manufactured by overlapping search.

**"One JSON array and nothing else."** The output is parsed and validated against
the pydantic model. Prose around the JSON is the most common cause of a scout's
whole return being discarded. The single-sentence exception for the empty case
exists because that sentence is genuinely valuable — it becomes the note on the
`Domain` node recording what was searched — and because a scout with no cards has
no other channel to report it.

**Pre-filling `discovered_by` and the `id` prefix.** Both are provenance fields the
orchestrator needs to be consistent, and neither is something a scout should
improvise. `discovered_by` is how a card is traced back to the pass that produced
it; the `id` prefix keeps card identifiers sortable by domain and makes duplicates
across runs collide visibly instead of silently coexisting.

## The output schema

JSON Schema, Draft 2020-12. This corresponds to a list of `AnalogyCard` as defined
in `src/reagent/contracts/proposal.py`; keep the two in sync, and if they ever
disagree, the pydantic model wins and this file is the bug.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://reagent.local/schemas/analogy-card-list.json",
  "title": "AnalogyCard list",
  "description": "The complete return value of one cross-domain scout. An empty array is valid and is an acceptable answer.",
  "type": "array",
  "items": { "$ref": "#/$defs/AnalogyCard" },
  "$defs": {
    "AnalogyCard": {
      "type": "object",
      "title": "AnalogyCard",
      "description": "A mechanism abstracted out of a non-biology domain. Write `mechanism` so that a reader cannot tell which domain it came from.",
      "additionalProperties": false,
      "required": [
        "id",
        "source_domain",
        "source_practice",
        "mechanism",
        "why_it_works_there",
        "structural_precondition",
        "discovered_by"
      ],
      "properties": {
        "id": {
          "type": "string",
          "minLength": 1,
          "description": "e.g. 'analogy:finance/regime-switching-ensemble'.",
          "pattern": "^analogy:[a-z0-9-]+/[a-z0-9-]+$"
        },
        "source_domain": {
          "type": "string",
          "minLength": 1,
          "description": "e.g. 'quantitative finance', 'cybersecurity'."
        },
        "source_practice": {
          "type": "string",
          "minLength": 1,
          "description": "What practitioners in that domain actually call and do."
        },
        "mechanism": {
          "type": "string",
          "minLength": 40,
          "description": "The transferable principle in domain-neutral language. No nouns specific to the source domain."
        },
        "why_it_works_there": {
          "type": "string",
          "minLength": 20,
          "description": "The evidence, in the source domain, that this practice works."
        },
        "structural_precondition": {
          "type": "string",
          "minLength": 20,
          "description": "What must be true of a problem for this mechanism to help. This is the field that makes the analogy checkable against our problem."
        },
        "citations": {
          "type": "array",
          "default": [],
          "items": { "type": "string", "minLength": 1 },
          "description": "Locators from the source domain (papers, patents, docs, books). Never fabricate one; a plain descriptive string is acceptable."
        },
        "discovered_by": {
          "type": "string",
          "minLength": 1,
          "description": "Scout agent / skill name, e.g. 'cross-domain-analogy/information-retrieval'."
        }
      }
    }
  }
}
```

### Where this schema is deliberately stricter than the pydantic model

Three tightenings, all intentional, and worth knowing about because a scout return
can satisfy the pydantic model and still be rejected by this schema, or the reverse.

- **`additionalProperties: false`.** The pydantic model ignores unknown keys by
  default. Forbidding them here catches a scout that invented a field — a
  `verdict`, a `confidence`, a `relevance_score` — which is a signal that it was
  reasoning about the destination it was told not to guess. Those inventions are
  useful diagnostics and should not be silently dropped.

- **`minLength: 1` on `id`, `source_domain`, `source_practice`, and
  `discovered_by`, and the `pattern` on `id`.** The model requires these fields but
  would accept an empty or malformed string. The pattern also enforces the
  `analogy:<domain-slug>/<practice-slug>` convention that the orchestrator relies
  on, and it will reject an identifier with capitals, spaces, or a missing slash.

- **`citations` is optional here, matching the model.** It has a default and is
  genuinely not required. That is a real allowance, not an oversight: a scout that
  can name a practice but honestly cannot locate a source should return the card
  with an empty citation list rather than fabricate one. Treat an empty
  `citations` array as a flag for the reviewer, not as an error.

Conversely, one model-level check has **no** JSON Schema equivalent and must be run
after parsing: the `_mechanism_is_abstract` validator, which rejects a card whose
`mechanism` is byte-identical to its `source_practice` after stripping and
lowercasing. That check is deliberately shallow — it catches only literal
copy-paste, and a scout that changed three words will pass it. The real abstraction
check is the human or orchestrator applying question 1 from the surface-resemblance
tests in [abstraction-ladder.md](abstraction-ladder.md). Do not mistake schema
validity for a card having climbed rung 2.

## The self-check rubric

Give this to the scout verbatim, in the position marked in the template. It is
written in the second person so the scout can apply it without translation.

```text
For each card you are about to return, answer these seven questions. If any answer
is no, either fix the card or drop it. Do not return a card with a "no".

1. ABSTRACTION. Delete every noun specific to my domain from `mechanism`. Is there
   still a sentence with a subject that does something? A reader who does not know
   my field must be unable to guess it from `mechanism` alone.

2. CAUSALITY. Does `mechanism` contain a "because" that names a structural feature
   of the situation — not a restatement ("because it is more robust") and not a
   result ("because it scores better")?

3. FALSIFIABILITY OF THE PRECONDITION. Can I name a plausible problem that
   `structural_precondition` excludes? If it excludes nothing, it is a truism.
   And does it exclude anything without merely redescribing my own domain?

4. THE TACIT CONDITION. Have I included the condition that my domain takes for
   granted — the one so reliably true here that we never write it down? If I
   cannot think of one, I have probably not looked hard enough; nearly every
   practice has at least one.

5. QUANTITY. Wherever the precondition depends on an amount — how many
   observations, how many items per group, how many rounds, how much history —
   have I said roughly how much, rather than only that some is needed?

6. CITATION HONESTY. Is every entry in `citations` something I have actually seen
   or can name precisely as a real work? Have I fabricated no identifier of any
   kind? Is a plain descriptive citation used wherever I lack a locator?

7. NECESSITY. If this card were dropped, would anything be lost? A card that
   restates a general principle everyone already applies is noise. Dropping it is
   free; returning it costs a reviewer's attention, which is the scarcest resource
   in this process.

Then, on the set as a whole: am I returning cards I do not believe in, because I
felt I should return something? If so, delete them. Zero cards with a note on what
I searched is a good answer and will be treated as one.
```

## Running the fan-out

The orchestrator's side of the contract, briefly.

- **Two to four domains per gap**, chosen by structural affinity using the shape
  table in [domain-map.md](domain-map.md). One scout each, spawned in parallel in a
  single message so they run concurrently.
- **Identical `{{RESTATED_PROBLEM}}` for every scout.** Vary only `{{DOMAIN}}`,
  `{{DOMAIN_SLUG}}`, and `{{DOMAIN_NOTES}}`. `{{DOMAIN_NOTES}}` should be the
  "where to search" paragraph from that domain's entry in the domain map, pasted in
  — it saves the scout a discovery pass and it keeps searches non-overlapping.
- **Parse and validate each return against the schema above, then against the
  pydantic model.** A return that fails to parse should be sent back once with the
  parse error, not silently dropped; scouts usually recover on the second attempt.
- **Write the `Domain` node for every scouted domain, including the ones that
  returned nothing**, with the scout's one-sentence note in the node attributes.
  The graph contract will reject an `Analogy` node with no `ORIGINATES_IN` edge to
  a `Domain`, so the domain nodes have to exist anyway, and creating them for empty
  returns is what makes "we searched there and found nothing" durable.
- **Then run Step 3 of the workflow** — abstract, ground against our actual
  problem, and search the target field for prior art — before writing a single
  `Proposal`. A card is not a proposal, and the gap between them is where the
  discard rate lives.
