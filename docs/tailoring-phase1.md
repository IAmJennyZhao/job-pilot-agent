# Tailoring source preparation

Phase 1 adds validated, versioned sources and local activation. It does not generate resumes or change application status. Candidate files and test artifacts belong in ignored storage.

## Verification checkpoints

- Step 1: baseline backend 66 tests passed; frontend typecheck passed. A consistent SQLite copy and existing v1 archive were saved privately before schema changes. Existing unrelated working-tree edits were preserved.
- Steps 2–8: pending implementation verification.

Use fictional fixtures in committed tests. Never commit candidate source text, generated application documents, or recovery archives.
