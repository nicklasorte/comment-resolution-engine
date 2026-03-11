# Codex Run Prompt: Comment Resolution Table Generation

Use this repository's tooling and prompt logic to generate a comment-resolution workbook.

## Tasks
1. Inspect the provided Excel comment matrix and identify these fields for each row:
   - comment number
   - comment text
   - line reference
   - status
   - revision/proposed change (if present)
2. Inspect the provided line-numbered PDF report for context when needed.
3. Map each comment to **report-ready proposed text** (1-3 sentences), written as language that could be inserted directly into the report.
4. Produce an output Excel table with at least:
   - `Comment Number`
   - `Proposed Report Text`
   - and preferably: `Insert Location`, `Comment Type`, `Source Line Reference`, `Status`
5. If status indicates completed/closed/resolved, mark the output status as `Complete` and leave proposed text blank unless new report text is explicitly required.

## Writing constraints
- Do not write meta-response language (e.g., "in response to comment").
- Write concise technical prose suitable for direct insertion into the report.
- Emphasize improvements to report clarity, methods, assumptions, and traceability.

## Run expectation
Execute the CLI to generate the initial structured workbook, then fill/adjust `Proposed Report Text` using the resolution logic from `prompts/resolution_engine.md`.
