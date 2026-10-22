# Tailoring source preparation

Phase 1 adds validated, versioned sources and local activation. It does not generate resumes or change application status. Candidate files and test artifacts belong in ignored storage.

## Verification checkpoints

- Step 1: baseline backend 66 tests passed; frontend typecheck passed. A consistent SQLite copy and existing v1 archive were saved privately before schema changes. Existing unrelated working-tree edits were preserved.
- Step 2: strict bank schema 4, preference schema 2, import/activation/preview contracts defined; supplied inputs parse without changing their bytes.
- Step 3: safe bounded YAML parsing checks duplicate keys/IDs, aliases, namespaces, eligibility, and dependency references. Supplied bank validates with 38 claims, 34 allowed, four excluded.
- Step 4: deterministic projection retains supported qualifiers and metrics while stripping archival text, contact data, excluded claims, mixed-dependency details, and future work. Nineteen fictional validation/projection tests pass.
- Step 5: additive migration adds immutable source versions, activation events, and a per-profile active pointer; repeated imports, stale activations, revocation, and cross-profile access are checked.
- Step 6: archive format v2 includes source text/snapshots in database rows; v1 archives upgrade with empty source tables. Restore validates source hashes, derived facts, and activation history before replacing data. Twenty-three storage/migration/backup tests pass.
- Steps 7–8: pending implementation verification.

## Storage and recovery

Source content remains unchanged after import. Activation/supersession/revocation are separate events; revoked versions cannot reactivate. Updating bank content requires a new bank version. Updating preferences or presentation creates a new bundle and requires activation. Source hashes establish local integrity, not authorship or independent verification.

Backups include private bank text, preferences, and template/style sources and must remain private. Restoring an older v1 archive restores its original data and leaves tailoring sources empty; the existing pre-restore recovery archive retains the replaced state. SQLite migrations prohibit updates to source/event rows; restore remains an explicit full-data replacement operation.

Use fictional fixtures in committed tests. Never commit candidate source text, generated application documents, or recovery archives.
