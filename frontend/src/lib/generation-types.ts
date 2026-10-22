import type { IntakeEvaluation } from "./intake-types";
export type GenerationState = "pending" | "running" | "completed" | "failed" | "interrupted";
export type GenerationRequest = { request_key: string; expected_input_hash: string; reviewed_description_hash: string; acknowledged_evaluation_hash: string };
export type GenerationWorkspace = {
  readiness: { ready: boolean; missing: string[]; input_hash: string | null; description_hash: string; description_reviewed: boolean; source_content: string; evaluation: IntakeEvaluation; saved_evaluation: IntakeEvaluation | null };
  runs: { id: string; state: GenerationState; created_at: string }[];
};
export type ResumeBullet = { id: string; record_id: string; evidence_ids: string[]; requirement_ids: string[]; text: string };
export type ResumeDraft = { schema_version: 1; requirements: { id: string; quote: string; description: string }[]; bullets: ResumeBullet[]; skills: { name: string; source_ids: string[] }[]; unmet_requirement_ids: string[]; change_summary: string[] };
export type AccuracyReport = { valid: boolean; validator_version: string; blocking_issues: string[]; supported_claim_ids: string[]; wording_changes: { bullet_id: string; before: string; after: string }[]; unmet_requirement_ids: string[]; human_review_required: true; scope: string };
export type GenerationRun = {
  id: string; job_id: string; state: GenerationState; parent_run_id: string | null; input_hash: string;
  source_changed: boolean; error: string | null; created_at: string; deadline_at: string;
  stages: { id: string; stage: "select" | "critique" | "revise" | "polish"; attempt: number; state: "running" | "passed" | "failed" | "interrupted"; output: unknown; validation: { valid: boolean; blocking_issues: string[] } | null; metadata: { reused_from_attempt?: string; latency_ms?: number; usage?: { input_tokens?: number; output_tokens?: number } }; error: string | null; started_at: string; finished_at: string | null }[];
  revision: { id: string; content_hash: string; plain_text: string; validation: AccuracyReport;
    content: { identity: { name: string }; education: Record<string, unknown>[]; records: Record<string, unknown>[]; section_order: string[]; draft: ResumeDraft } } | null;
  evidence: { id: string; record_id: string; text: string; constraints: string[] }[];
};
