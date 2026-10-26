import { redirect } from "next/navigation";

export default async function SkillsRedirect({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const legacy = await searchParams;
  const next = new URLSearchParams();
  for (const [key, raw] of Object.entries(legacy)) {
    const value = Array.isArray(raw) ? raw[0] : raw;
    if (value && key !== "tab") next.set(key, value);
  }
  next.set("tab", "skills");
  redirect(`/dashboard?${next}`);
}
