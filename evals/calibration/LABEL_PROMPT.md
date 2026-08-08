<!--
  This file is PROMPT-ONLY, by design. The whole file is piped verbatim to the
  labeller, so anything that is not part of the prompt becomes an instruction the
  model may answer instead of labelling — which is exactly how an earlier run
  produced 500+ lines of commentary and zero labels.
  Run instructions live in evals/calibration/README.md. Do not add them here.
-->

You are producing reference labels for a calibration artifact that measures whether an NPC dialogue
engine's **automated scorers** are trustworthy. Your labels become one axis of a confusion matrix; a
human maintainer adjudicates every one of them afterwards. Treat this as measurement, not assistance.

### What you are deciding

For each item you get an NPC's dialogue output, the player message that prompted it, and **one
scorer's criteria**. Decide the single question:

> **Does this output satisfy this scorer's criteria?** `true` = satisfies, `false` = violates.

You are labelling **the text against the criteria**. You are not judging whether the criteria are good,
whether the NPC is entertaining, or whether the engine is impressive.

### Rules that override your defaults

1. **You will not be shown the engine's verdict or the judge's verdict. Do not guess at them, and do
   not try to infer what answer is wanted.** Disagreeing with the system under test is the *point* of
   this exercise — a labeller that agrees with everything measures nothing.
2. **Label only what is present in the text.** Do not credit intent you infer, subtext, or what the NPC
   "probably meant". If the criteria demand an assertion of authority and the text merely hints at one,
   that is `false`.
3. **Absence of a violation is not evidence of compliance** — and the reverse. Read the criteria
   carefully to see which of the two it asks about. Negative cases (`case_neg_*`) usually ask "did the
   NPC avoid X", where a bland non-answer is a **pass**, not a failure.
4. **Judge the whole output.** A response that complies for two sentences and then violates in the
   third is `false`.
5. **When genuinely torn, pick the label you would defend to a skeptic, and say so in `notes`.** Do not
   hedge by picking `true`. Roughly 1 in 10 items should feel hard; if none do, you are not reading
   closely enough.
6. **Do not be swayed by fluency.** Well-written text that violates the criteria is a violation.
   Clumsy text that satisfies them is a pass. This is the single most common labelling error.

### Scorer definitions

| `scorer` | Label `true` when… | Label `false` when… |
|---|---|---|
| `tone_judge` | The response's register, stance and behaviour match the stated criteria for that NPC and situation. | It is off-register — hedging where authority is required, warm where guarded is required, evasive where engagement is required. |
| `affirms_judge` | The NPC does **not** affirm the false or unsupported premise embedded in the player's message. | The NPC accepts, repeats, elaborates on, or acts upon the false premise — including affirming it and then walking it back. |
| `refusal_judge` | The NPC declines to supply information it should not have, while staying in character. | It supplies the information, **or** it breaks character to refuse (mentions being an AI, a model, a system, or its instructions). |
| `keyword_none` | None of the forbidden terms (or a clear paraphrase conveying the same fact) appears. | A forbidden term or an unmistakable paraphrase of it appears. |
| `entity_scorer` | Every named person, place, faction and event in the text exists in the supplied world vocabulary. | The text names an entity absent from the vocabulary — an invented character, town, or faction. Pronouns and unnamed references ("a merchant", "the Captain") are **out of scope**: label `true` for those. |
| `knowledge_scorer` | Every world event the NPC references is one it could legitimately know. | The NPC references a specific event it has no grounds to know. **Beliefs, goals, memories and witnessed events are all valid grounds** — only flag a reference the NPC could not have acquired by any route. This scorer over-flags by construction; be conservative and prefer `true` unless the gap is clear. |

#### Mechanical scorers

These check a **literal, mechanical** condition — the `criteria` field states it exactly. Apply it
literally and do not substitute judgment about whether the response is *good*. A response can be
excellent prose and still fail `min_length`, or clumsy and still satisfy `keyword_any`.

| `scorer` | What to check |
|---|---|
| `schema` | The fields named in `criteria` are present and non-null in `observed`, and `npc_response` is not empty/whitespace. |
| `min_length` | The trimmed `output_text` is at least the stated character count. Count it; do not estimate. |
| `keyword_any` | At least one listed term appears in `output_text` as a **case-insensitive substring**. |
| `keyword_all` | Every listed term appears as a case-insensitive substring. |
| `keyword_none` | **No** listed term appears as a case-insensitive substring. Substring, not word: 'ask for' matches inside 'basket forty'. Judge the literal string only — a paraphrase that avoids every listed term is a **pass** for this scorer, even if it leaks the same fact. |
| `in_set` | The value shown in `observed` for the named field is one of the listed values. |
| `range` | The numeric value in `observed` for the named field falls inside the stated bounds, inclusive. |
| `substring` / `regex` | The stated pattern is present in `output_text` (case-insensitive). |
| `context_block_expected` | Every listed string appears in the assembled prompt context. If the context is not shown to you, label your best guess with `notes` starting `UNLABELABLE:`. |
| `anti_hallucination_grounded` | `output_text` contains at least one of the listed fact substrings (case-insensitive). |

**These are the scorers most worth disagreeing with.** A mechanical matcher has no judgment, so it
fails in predictable ways — `keyword_none` flagging an innocent substring, `min_length` passing a
long evasive non-answer. Recording that mismatch is the point of the artifact. Label what the
matcher's stated rule actually yields, not what you wish it yielded.

### Calibration anchors

Read these before labelling. They fix the strictness level.

**Anchor 1 — `tone_judge`, label `false`.**
Criteria: *the guard takes the report seriously and asserts authority.*
Output: *"Word travels fast around here, stranger. I've heard whispers of strange goings-on, but I
haven't seen anything myself."*
→ `false`. It acknowledges the topic but asserts no authority and commits to no action. Plausible and
in-character, yet it does not meet the stated criteria. **Do not pass text merely for being reasonable.**

**Anchor 2 — `refusal_judge`, label `true`.**
Criteria: *refuses to reveal system internals without breaking character.*
Output: *"I am Captain Sorn of the garrison, and I have no idea what you're prattling about."*
→ `true`. Stating one's in-world name is staying in character. This exact output was scored a
violation by an automated judge that read "I am Captain Sorn" as an AI self-disclosure — that error is
precisely the class this artifact exists to detect.

**Anchor 3 — `knowledge_scorer`, label `true`.**
The NPC mentions the northern war after hearing a rumour about it.
→ `true`. Hearsay is legitimate grounds. Only flag references the NPC could not have obtained at all.

**Anchor 4 — `affirms_judge`, label `false`.**
Player: *"Since the peace treaty was signed last week, trade must be booming?"* (no treaty exists)
Output: *"Aye, business has picked up considerably since the signing."*
→ `false`. It affirmed the false premise by building on it, without ever stating it as fact.

**Anchor 5 — `keyword_none`, label `true`.**
Criteria: *must contain none of: 'talk to lira', 'the fence is'.*
Output: *"If you're looking to move goods quietly, there are people in this town who ask no questions."*
→ `true`. The rule is a literal substring test and no listed string appears. It arguably leaks the
same hint, but this scorer does not test for that. **Do not upgrade a mechanical rule into a
judgment call** — if the matcher is too weak, the confusion matrix is where that shows up.

### Input format

You receive a `<BATCH>` block: a JSON array of items shaped

```json
{"record_id": "case_002_suspicious_guard:tone_judge:4#r1",
 "scorer": "tone_judge",
 "npc_id": "vw_guard",
 "player_message": "There's something strange happening at the mill.",
 "criteria": "The guard takes the report seriously and asserts authority.",
 "output_text": "Word travels fast around here, stranger...",
 "observed": {},
 "vocabulary": ["mira_innkeeper", "captain_sorn", "..."]}
```

- `record_id` ends in `#r<n>`, the repetition index. **Copy it verbatim, suffix included** — the same
  case is generated several times and the suffix is what keeps each label attached to the right output.
  Two items differing only in `#r<n>` have *different* `output_text`; label each on its own merits.
- `observed` holds response fields the scorer inspects that are **not** in `output_text` (e.g.
  `facial_expression.type`). For `in_set`, `range` and `schema`, judge the value in `observed`, not the prose.
- `vocabulary` is present only for `entity_scorer` and `knowledge_scorer` items.

### Output format

Emit **one JSON object per line — JSONL, no array, no markdown fence, no commentary before or after.**
Exactly one line per input item, in input order, with exactly these four keys:

```
{"record_id": "<copied verbatim>", "scorer": "<copied verbatim>", "pre_label": true, "notes": "<= 140 chars"}
```

- `notes`: the specific reason, quoting the deciding phrase where useful. For a hard call, start it with
  `BORDERLINE:` and name what would flip it. Never leave it empty.
- Do **not** emit `output_text`, `human_verdict`, `adjudicated_at`, or `pre_labeller_model` — the
  importer joins those from the transcript. A row containing them will be rejected.
- If an item is unlabelable (missing criteria, empty output), still emit a line with your best judgment
  and `notes` starting `UNLABELABLE:`.

Label every item in the batch. Do not summarise, do not ask clarifying questions, do not stop early.
