// Guards protect browser drafts from incompatible versions; server validation remains authoritative.
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const strings = (value: unknown) => Array.isArray(value) && value.every(v => typeof v === "string");
export const isRequestDraft = (value: unknown) => value === null || (object(value) && typeof value.fingerprint === "string" && typeof value.key === "string");
export const isIntakeDraft = (value: unknown) => object(value) && typeof value.source_url === "string" && typeof value.source_content === "string";
export function isIntakeReviewDraft(value: unknown): boolean {
  if (value === null) return true;
  if (!object(value) || !["company", "role_title", "category", "source_content"].every(k => typeof value[k] === "string")) return false;
  if (!["responsibilities", "required_skills"].every(k => strings(value[k]))) return false;
  if (!Array.isArray(value.links) || !value.links.every(v => object(v) && ["kind", "label", "url"].every(k => typeof v[k] === "string"))) return false;
  if (!["location", "remote_type", "summary", "pay_currency", "pay_period", "pay_raw", "status", "status_note", "notes"].every(k => value[k] == null || typeof value[k] === "string")) return false;
  if (!["pay_min", "pay_max", "extraction_confidence", "duplicateCount"].every(k => value[k] == null || typeof value[k] === "number")) return false;
  if (!["benefits", "extraction_warnings"].every(k => value[k] === undefined || strings(value[k]))) return false;
  if (value.sourceInput !== undefined && !isIntakeDraft(value.sourceInput)) return false;
  if (value.fullDescriptionReviewed !== undefined && typeof value.fullDescriptionReviewed !== "boolean") return false;
  return value.facts === undefined || (object(value.facts) && Object.values(value.facts).every(f => object(f) && (f.value === null || ["string", "number"].includes(typeof f.value)) && typeof f.quote === "string" && ["posting", "user", "unknown"].includes(String(f.origin))));
}
