# Tailoring source preparation

Phase 1 adds validated, versioned sources and local activation. It does not generate resumes or change application status. Candidate files and test artifacts belong in ignored storage.

## Verification checkpoints

- Step 1: baseline backend 66 tests passed; frontend typecheck passed. A consistent SQLite copy and existing v1 archive were saved privately before schema changes. Existing unrelated working-tree edits were preserved.
- Step 2: strict bank schema 4, preference schema 2, import/activation/preview contracts defined; supplied inputs parse without changing their bytes.
- Step 3: safe bounded YAML parsing checks duplicate keys/IDs, aliases, namespaces, eligibility, and dependency references. Supplied bank validates with 38 claims, 34 allowed, four excluded.
- Step 4: deterministic projection retains supported qualifiers and metrics while stripping archival text, contact data, excluded claims, mixed-dependency details, and future work. Nineteen fictional validation/projection tests pass.
- Step 5: additive migration adds immutable source versions, activation events, and a per-profile active pointer; repeated imports, stale activations, revocation, and cross-profile access are checked.
- Step 6: archive format v2 includes source text/snapshots in database rows; v1 archives upgrade with empty source tables. Restore validates source hashes, derived facts, and activation history before replacing data. Twenty-three storage/migration/backup tests pass.
- Step 7: Application Assets / Base Profile now supports import, source/claim/preferences/layout preview, exact-hash activation, history, and revocation. Desktop and mobile workflow tests pass, including reload and no AI calls. Frontend typecheck and production build pass.
- Step 8: full backend suite passes 98 tests. Four desktop/mobile browser checks cover new source lifecycle and existing profile draft editing. Frontend typecheck and production build pass. The real local database is migrated and its source bundle activated (34 allowed claims, four exclusions); original source bytes and all 18 pre-existing tables remain unchanged. Fresh-session reads and restoration of the actual v2 archive into an isolated database preserve all tables, attachments, and active facts. The actual pre-change v1 archive also validates with the new importer.

## Storage and recovery

Source content remains unchanged after import. Activation/supersession/revocation are separate events; revoked versions cannot reactivate. Updating bank content requires a new bank version. Updating preferences or presentation creates a new bundle and requires activation. Source hashes establish local integrity, not authorship or independent verification.

Backups include private bank text, preferences, and template/style sources and must remain private. Restoring an older v1 archive restores its original data and leaves tailoring sources empty; the existing pre-restore recovery archive retains the replaced state. SQLite migrations prohibit updates to source/event rows; restore remains an explicit full-data replacement operation.

## Using the feature

Open `/profile?tab=base` and expand **Import a source bundle** in Tailoring sources. Select the Markdown bank, YAML preferences, TeX layout reference, and Markdown style guide. **Import and validate** creates a pending version. Inspect the claims, exclusions, identity/education, preferences, and layout source, then check the review box and select **Activate reviewed sources**. Source changes require a new import and activation. **Revoke this version** blocks future use and keeps history.

Imports do not execute TeX, contact an AI provider, generate documents, or alter the existing profile/selected assets/jobs. Template safety and visual rendering are later-phase gates; an activated source bundle does not certify a compiler-ready template. The strict importer supports the supplied bank schema 4 and preferences schema 2. Other schema/validator versions require an explicit adapter rather than silently changing historical projections.

## Acceptance commands

- Backend: `py -3 -m pytest -q -p no:cacheprovider` — 98 passed.
- Frontend: `npm run typecheck` and `npm run build` — passed.
- UI: `npx playwright test --grep='profile draft|fictional tailoring sources'` — four passed across desktop/mobile. Synthetic screenshots were inspected; no candidate data is used by browser fixtures.
- Migration/recovery rehearsal: private database copies only, followed by the verified additive migration and source activation on the real local database. Pre-change SQLite/v1 backups and the post-activation v2 backup remain in ignored storage.

Windows sandbox restrictions required running pytest temporary-directory operations, Next.js build workers, browser tests, and Git commits with approved access outside the sandbox. The initially missing Playwright browser was installed. No live AI calls were made. Unrelated ignore-rule edits, page-architecture documentation, and mockups were left uncommitted and unchanged.

Use fictional fixtures in committed tests. Never commit candidate source text, generated application documents, or recovery archives.
