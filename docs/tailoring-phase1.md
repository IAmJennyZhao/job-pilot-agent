# Tailoring source preparation

Phase 1 adds validated, versioned sources and local activation. It does not generate resumes or change application status. Candidate files and test artifacts belong in ignored storage.

## Verification checkpoints

- Step 1: baseline backend 66 tests passed; frontend typecheck passed. A consistent SQLite copy and existing v1 archive were saved privately before schema changes. Existing unrelated working-tree edits were preserved.
- Step 2: strict bank schema 4, preference schema 2, import/activation/preview contracts defined; supplied inputs parse without changing their bytes.
- Step 3: safe bounded YAML parsing checks duplicate keys/IDs, aliases, namespaces, eligibility, and dependency references. Supplied bank validates with 38 claims, 34 allowed, four excluded.
- Step 4: deterministic projection retains supported qualifiers and metrics while stripping archival text, contact data, excluded claims, mixed-dependency details, and future work. Nineteen fictional validation/projection tests pass.
- Steps 5–8: pending implementation verification.

Use fictional fixtures in committed tests. Never commit candidate source text, generated application documents, or recovery archives.
