# Frozen compatibility archives

These compressed JSON backups were exported by the historical application commits in `manifest.json`, using only fictional test data. They are not current backups with a changed version number. The manifest records each original archive hash and the hashes of approved downloads.

| Version | Saved content |
| --- | --- |
| 1 | Job, follow-up and reusable resume text |
| 2–3 | Above plus an activated source bank with exclusions |
| 4 | Completed generation-v1 resume and its four stages |
| 5 | Generation-v1 resume with content review |
| 6 | Generation-v2 resume with preview receipt and approved PDF/TeX/text |
| 7 | Approved resume artifacts plus three reviewed cover-letter variants |

Tests restore each archive into a currently migrated SQLite database, verify history and approval boundaries, re-export with the current format, restore again, and check exact download hashes with model and compiler calls disabled. Version 3 has no saved intake decision; intake-history compatibility is covered by current roundtrip tests.

Keep these files unchanged when serializers, validators, prompts, layouts or dependencies change. A failed compatibility test is a migration/compatibility issue to investigate, not a reason to refresh the expected files.

For explicit fixture maintenance only, run `py -3 backend/tests/fixtures/freeze_compatibility.py` from the repository root. This executes tracked historical code in temporary checkouts under ignored backend storage. Generating versions 6–7 needs the local PDF toolchain; consuming the fixtures needs no compiler. No production database, private resume or live model is accessed. Source commits must still exist in Git history.
