# Integration with spectrum-systems

comment-resolution-engine implements SYS-001 and consumes architecture, schema, and governance defined in the spectrum-systems repository. Today, spectrum-systems is the source of truth for:
- Governing spec, schemas, and workflow contracts for SYS-001.
- Provenance guidance and error taxonomy definitions.
- System prompts and future rulepacks.

What remains local to this repository:
- Executable pipeline code, deterministic heuristics, and fallbacks.
- Local column mapping configuration and CLI UX.
- Built-in validation, clustering, generation, and export logic.

Planned future convergence:
- Load external rulepacks via `--rules-path/--rules-profile/--rules-version` once published in spectrum-systems.
- Align to updated schemas and provenance profiles from spectrum-systems without removing local deterministic behavior.
