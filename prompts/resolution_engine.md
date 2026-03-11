# Comment Resolution Engine Prompt

Use this prompt to fill NTIA-facing disposition fields in the comment resolution matrix.

## Outputs to fill
- **NTIA Comments**: concise internal disposition note.
- **Comment Disposition**: `Accept` or `Reject` only.
- **Resolution**: final report-ready text to insert or substitute in the report (no meta-commentary).

## Inputs available
- Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line
- Comment Type (`Technical`, `Clarification`, `Editorial/Grammar`)
- Agency Notes (primary concern)
- Agency Suggested Text Change (optional candidate wording)
- Optional Report Context from the line-numbered PDF

## How to use Agency fields
- Treat **Agency Notes** as the primary statement of the issue.
- Treat **Agency Suggested Text Change** as optional wording; use or refine it as needed.
- If both are present: understand the issue from notes, borrow language from suggested text when useful, and craft final NTIA Resolution independently.

## Disposition logic
- Technical: Accept when the comment identifies a substantive issue, missing assumption, unclear method, incorrect statement, unsupported claim, or needed qualification. Reject when incorrect, out of scope, already addressed, speculative, or would reduce precision.
- Clarification: Usually Accept when wording, purpose, assumptions, scope, applicability, or rationale are unclear. Reject when the report is already clear or added text would create clutter.
- Editorial/Grammar: Usually Accept when grammar/readability improves without changing meaning. Reject when it changes technical meaning or is unnecessary.

## Examples
- Accepted technical:  
  - NTIA Comments: "Accept. The comment highlights a missing modeling assumption that should be stated."  
  - Resolution: "The compatibility analysis assumes worst-case antenna pointing toward the victim receiver to ensure a conservative interference estimate."
- Rejected technical:  
  - NTIA Comments: "Reject. The report already documents this modeling assumption, so no change is required."  
  - Resolution: "No change to report text."
- Accepted clarification:  
  - NTIA Comments: "Accept. The purpose of the section needs clearer framing."  
  - Resolution: "The population impact metric estimates the population within modeled protection zones to contextualize study findings."
- Rejected clarification:  
  - NTIA Comments: "Reject. Existing language already explains the scope; further wording would be redundant."  
  - Resolution: "No change to report text."
- Accepted editorial:  
  - NTIA Comments: "Accept. Editorial change improves readability without altering meaning."  
  - Resolution: "Terminology is harmonized to use 'interference threshold' consistently across the section."
- Rejected editorial:  
  - NTIA Comments: "Reject. Proposed wording would change the technical meaning; existing text remains."  
  - Resolution: "No change to report text."

## Style rules for Resolution
- Write as final report language; do not mention the comment process.
- Keep it concise (sentence or short paragraph).
- Use active, specific prose; avoid placeholders unless the workbook convention requires them.

## When a row is already complete
- NTIA Comments: "Already completed."
- Comment Disposition: `Accept`
- Resolution: Keep existing Resolution if present; otherwise leave unchanged or use the local convention if one is provided.
