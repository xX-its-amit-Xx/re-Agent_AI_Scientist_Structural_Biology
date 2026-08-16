# Rendering the disclosure tree

Native `<details>` and `<summary>`, no JavaScript. The whole feature works with scripting
disabled, which matters because the publish target blocks external hosts and because a report
that needs JS to be readable is a report that is sometimes unreadable.

## Markup

```html
<details class="fu fu-what-is" id="fu-F-PRIOR-03-1">
  <summary>What is a binding pocket?</summary>
  <div class="fu-answer">
    <p>A dent on the protein's surface where a small molecule sits. …</p>
    <details class="fu fu-what-is" id="fu-F-PRIOR-03-1-1">
      <summary>What does it mean that the pocket "flexes"?</summary>
      <div class="fu-answer">…</div>
    </details>
  </div>
</details>
```

Four things this gets right for free: keyboard operation, screen-reader announcement of
expanded state, in-page find (see below), and print.

**Nest the children inside `.fu-answer`, not as siblings of it.** A child rendered as a sibling
of the answer text is announced by screen readers as a peer of the answer rather than as a
sub-question, and visually loses the indent that carries the hierarchy.

## Styling

Indent per level, and let the left border carry depth so a reader always knows how far down they
are:

```css
.fu { border-left: 2px solid var(--rule); padding-left: .75rem; margin: .4rem 0; }
.fu > summary {
  cursor: pointer; font-weight: 500;
  list-style: none;                 /* replace the default marker */
}
.fu > summary::before { content: "▸ "; color: var(--muted); }
.fu[open] > summary::before { content: "▾ "; }
.fu-answer { padding: .3rem 0 .1rem; }

/* Kind is a hue on the rule, matching the finding-kind palette. */
.fu-what-is   { border-left-color: #56B4E9; }
.fu-why       { border-left-color: #0072B2; }
.fu-how-known { border-left-color: #A6A6A6; }
.fu-so-what   { border-left-color: #009E73; }
.fu-objection { border-left-color: #D55E00; }
```

`list-style: none` on the summary is required — the default disclosure triangle is inconsistent
across browsers and cannot be positioned reliably. Supply your own marker.

Do not indent past about 2rem cumulative. At depth 5 a per-level indent of 0.75rem is already
3.75rem; on a narrow viewport that squeezes the text column badly. Cap the cumulative indent and
let the border colour plus the marker carry depth beyond level 3.

## In-page find

Browsers do not search inside a closed `<details>`, so a reader searching for a term will not find
its definition. Two mitigations, both cheap:

1. **Auto-open on `:target`**, so a deep link expands the branch and every ancestor:

```css
.fu:target { }                        /* the [open] attribute is set by the fragment */
```

`<details>` matched by the URL fragment is expanded automatically by modern browsers, and
ancestors expand with it. This is why every node needs a stable `id`.

2. **Emit a flat, visually hidden index** of every question and answer at the end of the report,
   so find-in-page and the browser's own text extraction reach the content even when collapsed:

```html
<div class="fu-index" aria-hidden="true">…all questions and answers, flattened…</div>
```

`aria-hidden` because a screen reader already has access through the tree, and announcing
everything twice is worse than not having the index.

## Stable ids

`fu-<finding-id>-<path>` where path is the 1-indexed child position at each level:
`fu-F-PRIOR-03-1-2-1`. Derived from position in `sorted_children()`, not from question text, so
the id survives rewording.

The consequence to accept: reordering branches changes ids and breaks old deep links. That is the
right trade — ids derived from question text break on every copy-edit instead, which is far more
frequent.

## Print

```css
@media print {
  .fu { break-inside: avoid; }
  .fu > .fu-answer, .fu[open] > .fu-answer { display: block !important; }
  .fu > summary::before { content: ""; }
  .fu-index { display: none; }
}
```

Everything expands on print, because a printed collapsed disclosure is a question with no answer,
which is worse than no disclosure. Note that `details:not([open]) .fu-answer` is hidden by the UA
stylesheet rather than by ours, so the `!important` is doing real work here.

## Default open state

Everything closed except the lede, with one exception: **if a finding's `follow_ups` is its only
explanation — no `interpretation` — open the first branch**, so the reader is not left with a bare
claim and a widget.

Do not open by depth or by kind. A tree that starts half-open reads as a wall of text with
decorative arrows, and loses the property that made the top level skimmable.

## Reading-time hint

Optional and useful: a count on the summary when a branch is large.

```html
<summary>What is a binding pocket? <span class="fu-count">3 more</span></summary>
```

It tells the reader whether clicking commits them to a sentence or a section. Show it only when a
branch has children; on a leaf it is noise.

## Accessibility notes

- `<summary>` is a button. Do not put interactive controls inside one — nested interactive content
  is not reliably reachable by keyboard.
- Keep the question text *in* the summary, not in a `title` attribute. Tooltips are invisible to
  keyboard users and unreliable on touch.
- Do not rely on the border hue alone to convey kind. It is a redundant channel; the question
  wording carries the meaning.
- Contrast the marker and border against both themes. The palette above is Okabe-Ito, which holds
  up on light and dark grounds, but the `--rule` fallback must be defined for both.

## What not to build

**No "expand all" button.** It defeats the purpose and produces the unreadable wall the feature
exists to avoid. Print already does this for the case that needs it.

**No animation.** A transition on `<details>` requires JS or a height hack, both of which break
the no-script guarantee for a cosmetic gain.

**No lazy loading.** Trees are small — fifteen nodes of prose is a few kilobytes. Rendering all of
it inline keeps the page self-contained, which the publish target requires anyway.
