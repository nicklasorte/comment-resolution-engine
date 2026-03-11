# Comment Resolution Engine Prompt

## Purpose
Transform agency comments into concise **report-ready text** that can be inserted directly into the study report.

## Inputs
- Comment matrix row with at least comment number and comment text.
- Optional line number reference.
- Optional existing revision notes.
- Optional status (e.g., complete/completed/open).
- Optional PDF report context.

## Output Requirements
For each row produce:
1. `Comment Number`
2. `Proposed Report Text` (1-3 sentences)
3. Optional: `Insert Location`, `Comment Type`, `Source Line Reference`, `Status`

## Critical Writing Rule
Write as final report language, not as commentary about the comment process.

- Bad: "In response to the comment, the report now clarifies..."
- Good: "The compatibility analysis assumes worst-case antenna pointing toward the victim receiver to ensure a conservative interference assessment."

## Comment Classification Categories
- Technical: assumptions, methods, calculations, modeling, evidence.
- Clarification: requests for clearer explanation/definitions.
- Editorial: grammar, style, formatting, typo.
- Scope/Process: request outside report scope or administrative notes.
- General: anything not clearly in categories above.

## Style Rules
- Use plain, specific technical prose.
- Keep each row to 1-3 sentences.
- Prefer active voice.
- Do not mention reviewers, comments, or responses.
- Avoid defensive language or debate.
- If data are unknown, use neutral placeholders and identify insertion location.

## Handling Completed Rows
If status is `completed`, `complete`, `closed`, or `resolved`:
- Set status to `Complete`.
- Keep `Proposed Report Text` blank unless revised report text is explicitly supplied.
- Preserve row metadata (comment number, references).

## Examples
### Example A (Technical)
Input comment: "Assumptions for antenna pointing are not conservative."
Output text: "The interference analysis assumes worst-case main-lobe antenna alignment toward the victim receiver, yielding a conservative upper-bound estimate of received interference."

### Example B (Clarification)
Input comment: "Please define aggregate interference metric."
Output text: "Aggregate interference is defined as the sum of co-channel and adjacent-channel contributions at the receiver input, expressed in dBm over the specified analysis bandwidth."

### Example C (Editorial)
Input comment: "Typo in line 204."
Output text: "Section 4.2 replaces 'intereference' with 'interference' for consistency with the terminology used throughout the report."
