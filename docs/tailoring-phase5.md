# Phase 5 — Rendering and downloads

Implemented after the Phase 1–4 consolidation. No model calls occur during rendering, preview, approval, downloads, cleanup or restore.

## Workflow

1. Recover a browser draft, or save and validate edits. Compatible existing drafts keep their original parent and request identity; incompatible or damaged drafts remain available as an exact JSON download until explicitly discarded.
2. Mark the saved content reviewed. This existing action still confirms content/evidence only.
3. Render the current valid saved revision and open its PDF preview. Rendering may also precede content review. The preview shows every page as an image and provides the actual PDF for full-size inspection.
4. Inspect layout and confirm final approval. Both a recorded preview receipt and explicit layout acknowledgment are required. The server checks the current revision, content review, validation, source eligibility, one-page report and exact artifact manifest again under a write lock.
5. Download PDF, TeX or UTF-8 text, or copy approved text. All exports come from the same frozen presentation and stored artifact bytes. Selecting a historical revision exposes its approved exports. Source/job changes warn in the review workspace and block new approvals, but do not rewrite historical exports.

Layout corrections use the existing editor and append a new revision. No export operation shortens content, shrinks fonts, calls a model, marks a job applied, or promotes a generated resume into a reusable asset.

## Presentation and compatibility

`resume-layout-v1` is owned application code: US Letter, Latin Modern, 11 pt body, 10 pt project technology lines, 23 pt name, 0.6 inch side margins, 0.42 inch vertical margins, and Education → Technical Skills → Experience → Projects. The supplied style guide's preamble is preserved. Imported template/style text is retained and hashed as provenance; it is never executed. Future layout changes must introduce a new renderer version while retaining the old verifier.

The shared public presentation contains approved identity/contact information, relocation display, education, selected skills, employment metadata, project metadata and bullets. Skills use three public category labels; editorial source labels, evidence IDs, notes, preferences, exclusions and unmet requirements never export. Project subtitles/URLs come from the original immutable approved source bank. Project technology lines are restricted to technologies explicitly supported by selected eligible claims. This render-only metadata is independently frozen and verified against that source during restore. Historical generation snapshots, plain text, content hashes and content approvals are unchanged.

Existing generation versions 1 and 2 remain supported. Legacy content approvals do not imply PDF approval. Read-only requests never render, and downloads never recompile missing or corrupted bytes.

## Storage and backup

Migration `0008_resume_exports` adds immutable `resume_renders`, `resume_preview_receipts`, and `resume_export_approvals`. SQLite update triggers protect each table. A render stores PDF/TeX/text bytes as base64 inside a JSON bundle, individual SHA-256 checksums, compiler identity, renderer/template hashes, presentation, layout report, and content/input/validation hashes. This keeps file publication and database persistence atomic and eliminates durable filesystem orphans.

Backup format 6 includes these tables and exact artifact bytes. Formats 1–5 adapt to empty artifact tables. Validation checks references, source metadata, content review, reconstructed TeX/text, PDF text/page checks, checksums, receipts and final approvals before replacing live data. Historical downloads work after restore without an installed compiler. The existing pre-restore recovery archive and 50 MB total archive limit remain in force.

Unapproved previews can be removed explicitly; their receipts and bytes are removed together. Approved exports are retained. Source banks, master resumes, application attachments and revision history are not cleanup targets. Compiler files use random directories under private `storage/render-tmp`, are removed on success/failure/timeout, and abandoned directories older than one hour are swept on the next render. Redirected scratch paths and symlink/junction cleanup targets are rejected/skipped.

## Local setup

Install backend dependencies with `py -3 -m pip install -e '.[dev]'` from `backend` (use `python` on other platforms). PDF inspection and page previews use PyMuPDF 2.0, pinned to preserve the tested extraction and layout-check behavior.

Install **TeX Live pdfLaTeX**, with `lm`, `microtype`, `enumitem`, `titlesec`, `geometry`, and `hyperref`, plus the standard LaTeX/font encoding packages. Use an existing `pdflatex` on PATH or set `RESUME_PDFLATEX` to its executable. A Windows portable installation at `backend/storage/texlive/bin/windows/pdflatex.exe` is detected automatically. The implementation was verified with pdfTeX 1.40.29 / TeX Live 2026, installed privately in that directory without changing system PATH or file associations. Toolchain files and personal QA outputs are ignored, not committed or included in app backups.

Official setup/flag references: [TeX Live portable installation](https://tug.org/texlive/doc/install-tl.html), [TeX Live documentation](https://tug.org/texlive/doc/texlive-en/texlive-en.html).

Rendering disables shell escape, first-line format directives, and automatic font/format generators; it provides no model credentials or user-supplied search paths to the child process. It uses a 30-second deadline, 200 KB TeX input cap, 15 MB temporary-output cap, 5 MB PDF cap and two concurrent compiler slots per process. No network fetching or automatic package installation occurs during rendering. Missing compiler/packages, unsupported characters and timeouts return actionable errors without changing the saved revision.

Checks cover one page, Letter dimensions, text reading order/parity, font-size floor, safe margins, overfull boxes, missing glyphs and permitted links. PDF active actions/attachments are rejected. These deterministic checks supplement human layout review; they do not claim independent factual verification or complete detection of every visual collision.

## Verification

- Backend tests cover real compilation, overflow, special characters/Unicode, TeX injection as literal text, URLs, timeout cleanup, source exclusions, exact downloads, stale/concurrent edits, source revocation, approvals, backup 6 and legacy restore, tampering, and migration immutability.
- Browser tests cover desktop/mobile preview, approval gating, byte-matching downloads, historical navigation, source-change warnings, unsaved and incompatible draft recovery, and unapproved-preview removal. Existing cross-tab recovery tests remain applicable.
- The three saved writing-evaluation drafts (AI, backend and full-stack) are compiled locally for visual QA without new model requests or changes to application records. Private results are under `backend/storage/phase5-qa/`.

Completion checks: 193 backend tests passed; all 40 desktop/mobile browser tests passed; TypeScript checking and the production build passed. All three representative private PDFs passed one-page/text/layout checks and visual inspection. The legacy-v1 export round trip was also exercised explicitly after the full suite.

Run `py -3 -m pytest -q -p no:cacheprovider` in `backend`; run `npm run typecheck`, `npx playwright test`, and `npm run build` in `frontend`. Real render tests require the documented compiler installation.
