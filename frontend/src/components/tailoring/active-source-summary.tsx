"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import type { TailoringSourceSummary } from "@/lib/types";

export const sourceStatusExplanation: Record<TailoringSourceSummary["status"], string> = {
  pending: "Imported for review. It is not used for new generations until explicitly activated.",
  active: "This version supplies the allowed facts for new resume and cover letter generations.",
  superseded: "Another version replaced this activation. Its facts and activation history are preserved.",
  revoked: "Unavailable for new generations. A revoked version cannot be reactivated."
};

/** Display the existing source registry; never infer activation from library/profile content. */
export function ActiveSourceSummary({ onManage, showManage = true, expectedSourceId, onRefreshPreparation }: {
  onManage?: () => void;
  showManage?: boolean;
  expectedSourceId?: string | null;
  onRefreshPreparation?: () => void;
}) {
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const sources = useQuery({ queryKey: ["tailoring-sources", profile.data?.id], queryFn: api.tailoringSources, enabled: Boolean(profile.data?.id) });
  const current = sources.data?.versions.find(version => version.id === sources.data.active_id);
  const pending = sources.data?.versions.filter(version => version.status === "pending").length ?? 0;
  const error = profile.error || sources.error;
  const loading = profile.isPending || Boolean(profile.data && sources.isPending);
  const inconsistent = Boolean(sources.data?.active_id && (!current || current.status !== "active"));
  const changed = expectedSourceId !== undefined && sources.data && sources.data.active_id !== expectedSourceId;

  return <aside aria-label="Active tailoring source" data-source-id={!error && !inconsistent ? current?.id ?? "" : ""} className="grid min-w-0 gap-3 rounded-md border border-border bg-muted/30 p-4 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold">Active tailoring sources</h3>
      <Badge tone={error || inconsistent ? "warn" : current ? "good" : "neutral"}>{loading ? "Checking sources" : error || inconsistent ? "Status unavailable" : current ? "Activated version" : "No active bundle"}</Badge>
    </div>
    {error || inconsistent ? <div role="alert">{error ? `Could not check source status: ${error.message}` : "The active version could not be verified."}<Button variant="ghost" size="sm" onClick={() => { profile.refetch(); sources.refetch(); }}>Reload source status</Button></div> : loading ? <p>Loading the source registry…</p> : current ? <>
      <p className="flex flex-wrap gap-x-4 gap-y-1"><span>Version <strong>{current.bank_version}</strong></span><span>{current.eligible_count} allowed {current.eligible_count === 1 ? "claim" : "claims"}</span><span>{current.excluded_count} excluded {current.excluded_count === 1 ? "claim" : "claims"}</span></p>
      <p className="text-muted-foreground">Only allowed facts can be used. Each generated document still needs its own review.</p>
    </> : <p className="text-muted-foreground">{profile.data ? "Import and explicitly activate a reviewed source version to supply facts for tailoring." : "Save a base profile, then import and activate reviewed tailoring sources."}</p>}
    {!error && !loading && pending > 0 ? <p>{pending} pending {pending === 1 ? "version awaits" : "versions await"} review. Importing does not replace the active bundle.</p> : null}
    {changed && !error && !inconsistent ? <p role="status" className="text-warning-foreground">Source activation changed since preparation was loaded. {onRefreshPreparation ? <Button variant="ghost" size="sm" onClick={onRefreshPreparation}>Refresh preparation</Button> : "Refresh preparation before generating."}</p> : null}
    <details><summary className="cursor-pointer font-medium">Source boundaries and identifiers</summary><div className="mt-2 grid gap-2 text-muted-foreground">
      <p>Profile edits, resume merges and library status changes do not update or activate this bundle. Excluded claims remain unavailable.</p>
      <p>Source activation, saved document content review and final resume PDF approval are separate decisions. Imported layout files are references; their TeX is not executed.</p>
      {current && !error && !inconsistent ? <p className="break-all text-xs">Bundle: {current.bundle_hash}</p> : null}
    </div></details>
    {showManage ? onManage ? <Button variant="ghost" size="sm" className="w-fit px-0 text-primary underline" onClick={onManage}>Manage tailoring sources</Button> : <Link className="w-fit text-primary underline" href="/profile?tab=sources">Manage tailoring sources</Link> : null}
  </aside>;
}
