import { z } from "zod";

const id = z.string().min(1).max(128);
const bullet = z.object({ id, record_id: id, text: z.string().max(1800), evidence_ids: z.array(id).min(1).max(6), requirement_ids: z.array(id).max(40) }).strict();
const skill = z.object({ name: z.string().min(1), source_ids: z.array(id).min(1) }).strict();
const edit = z.object({ bullets: z.array(bullet).max(20), skills: z.array(skill).max(40), project_order: z.array(id).max(20) }).strict();
const saved = z.object({ expected_revision_id: id, request_key: z.string().max(128), edit }).strict();
const restored = z.object({ expected_revision_id: id, request_key: z.string().max(128), revision_id: id }).strict().nullable();

export const acceptsResumeDraft = (value: unknown) => saved.safeParse(value).success;
export const acceptsResumeRestore = (value: unknown) => restored.safeParse(value).success;
