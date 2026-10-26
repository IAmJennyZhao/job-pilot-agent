import { redirect } from "next/navigation";

export default async function ReportsRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const legacy = await searchParams;
  const next = new URLSearchParams();
  for (const [key, raw] of Object.entries(legacy)) {
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value && key !== "tab") next.set(key === "since" || key === "saved_since" ? "outcomesSince" : key === "dimension" ? "group" : key, value);
  }
  next.set("tab", "outcomes");
  redirect(`/dashboard?${next}`);
}
