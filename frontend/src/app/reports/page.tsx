import { redirect } from "next/navigation";
import { analyticsSince } from "@/lib/analytics-cohort";

export default async function ReportsRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const legacy = await searchParams;
  const next = new URLSearchParams();
  for (const [key, raw] of Object.entries(legacy)) {
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value !== undefined && key !== "tab") next.set(key === "dimension" ? "group" : key, value);
  }
  // Retain conflicting aliases so the shared filter can explain precedence.
  if (!next.has("since") && (next.has("saved_since") || next.has("outcomesSince"))) next.set("since", analyticsSince(next));
  next.set("tab", "outcomes");
  redirect(`/dashboard?${next}`);
}
