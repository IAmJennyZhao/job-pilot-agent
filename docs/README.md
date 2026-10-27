# JobPilot documentation

| Guide | Purpose |
| --- | --- |
| [Project README](../README.md) | Features, installation, configuration and local commands |
| [Page architecture](page-architecture.md) | Navigation, ownership, URL compatibility and state/approval contracts |
| [Verification](verification.md) | Regression commands, CI scope and verification limits |
| [Portfolio screenshots](assets/screenshots/README.md) | Fictional-data images, captions, alt text and capture instructions |

## Document workflows

The implementation and its contract tests are the reference for generation and historical documents:

| Area | Implementation |
| --- | --- |
| Immutable tailoring sources | [Source service](../backend/app/services/tailoring_source_service.py), [schemas](../backend/app/tailoring_schemas.py) |
| Current resume writer | [Generation coordinator](../backend/app/services/resume_v6_generation.py), [composition](../backend/app/services/resume_v6.py) |
| Saved content review/editing | [Resume review](../backend/app/services/resume_review.py), [validation](../backend/app/services/resume_review_validation.py) |
| PDF preview and exact exports | [Rendering](../backend/app/services/resume_rendering.py), [bounded compiler](../backend/app/services/resume_compiler.py) |
| Cover letters | [Generation/review](../backend/app/services/cover_letters.py), [validation](../backend/app/services/letter_validation.py) |
| Historical compatibility | [Frozen fixture guide](../backend/tests/fixtures/compatibility/README.md), [backup regressions](../backend/tests/test_historical_backups.py) |

Local mockups, execution notes, historical audit reports and superseded recordings are excluded from version control. They are preserved in the development workspace. Public screenshots contain only fictional data.
