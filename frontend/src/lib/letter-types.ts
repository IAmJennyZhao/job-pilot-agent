import { z } from "zod";
import type { GenerationRequest, GenerationRun, GenerationWorkspace } from "./generation-types";
import type { ReviewWorkspace } from "./review-types";

export const letterSentence = z.object({
  id: z.string(), text: z.string(), sentence_kind: z.enum(["candidate_claim", "job_context", "motivation", "transition"]),
  candidate_evidence_ids: z.array(z.string()), job_evidence_ids: z.array(z.string())
}).strict();
export const letterEdit = z.object({ variants: z.array(z.object({ variant_id: z.string(),
  angle: z.enum(["concise professional", "technical contribution", "product/user impact"]),
  paragraphs: z.array(z.object({ sentences: z.array(letterSentence).min(1).max(10) }).strict()).min(1).max(5)
}).strict()).min(1).max(3) }).strict();
export type LetterEdit = z.infer<typeof letterEdit>;
export type LetterSentence = z.infer<typeof letterSentence>;
export type LetterOptions = { count: number; length: "short" | "standard"; template_id: string | null;
  company_context?: { text: string; source_url: string; confirmed: true } | null };
export type LetterRequest = GenerationRequest & { options: LetterOptions };
export type LetterWorkspace = GenerationWorkspace & { templates: { id: string; title: string }[] };
export type LetterRun = Omit<GenerationRun, "revision" | "stages"> & {
  revision: { id: string; content: LetterEdit; content_hash: string; plain_text: string } | null;
  stages: { id: string; stage: string; attempt: number; state: string; error: string | null;
    validation: { valid: boolean; issues: { field_path: string; message: string }[] } | null }[];
};
export type LetterReview = Omit<ReviewWorkspace, "revision" | "changes_from_baseline" | "changes_from_parent"> & {
  revision: Omit<ReviewWorkspace["revision"], "edit" | "content"> & { edit: LetterEdit; content: LetterEdit };
  variant_texts: string[];
  job_evidence: { id: string; text: string }[];
  changes_from_baseline: { field_path: string; before: unknown; after: unknown }[];
  changes_from_parent: { field_path: string; before: unknown; after: unknown }[];
  checks: { id: string; revision_id: string; state: string; error: string | null }[];
  sentence_assessment: { sentences: { sentence_id: string; actual_kind: string; supported: boolean; explanation: string;
    supports: { source_kind: string; source_id: string; quote: string }[] }[] } | null;
};
export const letterLocalDraft = z.object({ version: z.literal(1), base: z.string(), key: z.string(), edit: letterEdit }).strict();
export type LetterLocalDraft = z.infer<typeof letterLocalDraft>;
export const letterRequestNonce = z.object({ fingerprint: z.string(), key: z.string() }).strict().nullable();
export const letterCheckNonce = z.object({ revision: z.string(), key: z.string() }).strict().nullable();
export const letterContextDraft = z.object({ text: z.string(), source_url: z.string(), confirmed: z.boolean() }).strict();
