import type { ResumeBullet, ResumeDraft, GenerationRun } from "./generation-types";

export type ResumeEdit = { bullets: ResumeBullet[]; skills: ResumeDraft["skills"]; project_order: string[] };
export type SaveResumeEdit = { request_key: string; expected_revision_id: string; edit: ResumeEdit };
export type RestoreResumeRevision = { request_key: string; expected_revision_id: string; revision_id: string };
export type ReviewResume = { revision_id: string; content_hash: string; validation_hash: string; input_hash: string };
export type ResumeRender = {
  id: string; revision_id: string; manifest_hash: string; content_hash: string; created_at: string;
  renderer_version: string; engine: string; approved_at: string | null; hashes: Record<"pdf" | "tex" | "txt", string>;
  validation: { valid: boolean; pages: number; issues: string[]; human_layout_review_required: boolean };
};
export type ResumeRenderPreview = { preview_receipt_id: string; manifest_hash: string; pdf_base64: string; page_images: string[] };
export type ResumeChange = { field: string; kind: string; before: unknown; after: unknown };
export type ReviewWorkspace = {
  baseline_id: string; run_id: string; job_id: string; profile_id: string; current_revision_id: string; input_hash: string; source_problem: string | null;
  revision: { id: string; sequence: number; origin: string; parent_id: string | null; restored_from_id: string | null;
    content: NonNullable<GenerationRun["revision"]>["content"]; content_hash: string; plain_text: string; edit: ResumeEdit;
    validation: { valid: boolean; validator_version: string; issues: { field_path: string; message: string }[]; validated_content_hash: string; input_hash: string; unmet_requirement_ids: string[]; human_review_required: true };
    validation_hash: string; created_at: string };
  approval: { id: string; reviewed_at: string; content_hash: string } | null; approval_eligible: boolean; approved_current: boolean;
  history: { id: string; sequence: number; origin: string; created_at: string; valid: boolean; reviewed: boolean }[];
  changes_from_baseline: ResumeChange[]; changes_from_parent: ResumeChange[];
  evidence: GenerationRun["evidence"];
  records: { id: string; kind: string; employer?: string; title_display?: string; name?: string; start?: string; end?: string }[];
  skill_groups: { id: string; label: string; values: string[] }[];
  technology_catalog: { id: string; name: string; aliases: string[] }[];
};
