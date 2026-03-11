# Codex Run Prompt: Comment Resolution Table Generation

Use this repository's tooling and prompt logic to generate an NTIA comment-resolution workbook.

## Tasks
1. Inspect the provided Excel comment matrix and identify these fields for each row:
   - Comment Number, Reviewer Initials, Agency, Report Version, Section, Page, Line
   - Comment Type (Technical, Clarification, Editorial/Grammar)
   - Agency Notes (primary concern)
   - Agency Suggested Text Change (optional wording)
2. Inspect the provided line-numbered PDF report for context when available.
3. Produce:
   - `NTIA Comments` (concise internal disposition note)
   - `Comment Disposition` (`Accept` or `Reject`)
   - `Resolution` (final report-ready text, not meta-commentary)
4. Preserve existing workbook columns when possible; fill the NTIA columns rather than creating duplicates.

## Writing constraints
- Do not write meta-response language (e.g., "in response to the comment").
- Write concise technical prose suitable for direct insertion into the report.
- Use agency suggested text when helpful; otherwise craft clear NTIA wording.

## Run expectation
Execute the CLI to generate the structured workbook, then refine `NTIA Comments`, `Comment Disposition`, and `Resolution` using the resolution logic from `prompts/resolution_engine.md`.
