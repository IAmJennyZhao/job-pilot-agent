import type { JobCreatePayload, JobDuplicateCandidate } from "./types";

export type IntakeFact = { value: string | number | null; quote: string; origin: "posting" | "user" | "unknown" };
export type IntakeFactKey = "role_family" | "employment_type" | "salary_component" | "salary_band" | "nyc_compatible" | "employer_source" | "required_years" | "preferred_years" | "company_stage" | "employee_count" | "hours_week";
export type IntakeFacts = Partial<Record<IntakeFactKey, IntakeFact>>;
export type IntakeReview = { job: JobCreatePayload; facts: IntakeFacts; full_description_reviewed: boolean };
export type IntakeEvaluation = {
  available: boolean; source_id: string | null; preference_hash: string | null; preference_version: string | null;
  input_hash: string; evaluation_hash: string; message: string; full_description_ready: boolean;
  flags: { key: string; level: "red" | "amber" | "green"; message: string; secondary: boolean; evidence: IntakeFact | null }[];
  duplicate_candidates: JobDuplicateCandidate[];
};
export type IntakeSave = IntakeReview & { request_key: string; decision: "save_later" | "continue"; expected_evaluation_hash: string; allow_duplicate: boolean };
export type IntakePreparation = {
  saved_evaluation: IntakeEvaluation | null; current_evaluation: IntakeEvaluation | null; review_stale: boolean;
  sources_ready: boolean; full_description_ready: boolean; generation_available: boolean; decision: string | null;
};
