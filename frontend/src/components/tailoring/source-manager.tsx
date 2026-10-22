"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/field";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { TailoringSourceImport, TailoringSourcePreview } from "@/lib/types";

const fields: Array<{ key: keyof TailoringSourceImport; label: string; accept: string; limit: number }> = [
  { key: "bank_markdown", label: "Experience bank (.md)", accept: ".md", limit: 524288 },
  { key: "preferences_yaml", label: "Job preferences (.yaml)", accept: ".yaml,.yml", limit: 65536 },
  { key: "template_tex", label: "Resume layout (.tex)", accept: ".tex", limit: 65536 },
  { key: "style_guide", label: "Layout style guide (.md)", accept: ".md", limit: 65536 }
];

export function TailoringSourceManager({ profileId }: { profileId: string }) {
  const cache = useQueryClient();
  const [files, setFiles] = React.useState<Partial<Record<keyof TailoringSourceImport, File>>>({});
  const [selected, setSelected] = React.useState("");
  const [reviewedHash, setReviewedHash] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState("");
  const [localError, setLocalError] = React.useState("");
  const versions = useQuery({ queryKey: ["tailoring-sources", profileId], queryFn: api.tailoringSources });
  const sourceId = selected || versions.data?.active_id || versions.data?.versions[0]?.id || "";
  const preview = useQuery({ queryKey: ["tailoring-source", profileId, sourceId], queryFn: () => api.tailoringSource(sourceId), enabled: Boolean(sourceId) });
  const source = preview.data;

  function refreshed(data: TailoringSourcePreview) {
    setSelected(data.id);
    setReviewedHash(null);
    cache.setQueryData(["tailoring-source", profileId, data.id], data);
    cache.invalidateQueries({ queryKey: ["tailoring-sources", profileId] });
    cache.invalidateQueries({ queryKey: ["tailoring-source", profileId] });
  }

  const importSource = useMutation({
    mutationFn: async () => {
      const payload = {} as TailoringSourceImport;
      for (const field of fields) {
        const file = files[field.key];
        if (!file || file.size > field.limit) throw new Error(`${field.label}: choose a file under ${field.limit / 1024} KB.`);
        // Fatal UTF-8 decoding preserves source bytes instead of silently replacing invalid text.
        payload[field.key] = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer());
      }
      return api.importTailoringSource(payload);
    },
    onSuccess: data => { refreshed(data); setNotice("Imported for review. Existing activation is unchanged."); }
  });
  const activate = useMutation({
    mutationFn: () => api.activateTailoringSource(source!.id, source!.bundle_hash, versions.data!.active_id),
    onSuccess: data => { refreshed(data); setNotice("Source version activated. Excluded claims remain unavailable."); },
    onError: () => { setReviewedHash(null); versions.refetch(); preview.refetch(); }
  });
  const revoke = useMutation({
    mutationFn: () => api.revokeTailoringSource(source!.id, source!.bundle_hash, versions.data!.active_id),
    onSuccess: data => { refreshed(data); setNotice("Source version revoked. Its history is preserved."); },
    onError: () => { versions.refetch(); preview.refetch(); }
  });
  const busy = importSource.isPending || activate.isPending || revoke.isPending;
  const error = localError || importSource.error?.message || activate.error?.message || revoke.error?.message || versions.error?.message || preview.error?.message;
  const mayActivate = source && source.status !== "active" && source.status !== "revoked" &&
    ["approved", "approved_with_exclusions"].includes(source.approval.status) && source.eligible_count > 0;

  return <div role="region" aria-label="Tailoring sources"><Panel className="mt-6 grid gap-4">
    <div>
      <h2 className="text-lg font-semibold">Tailoring sources</h2>
      <p className="text-sm text-muted-foreground">Choose which approved facts future resumes may use. Importing a version keeps it pending until you review and activate it.</p>
    </div>
    {notice ? <p role="status" className="text-sm">{notice}</p> : null}
    {error ? <div role="alert" className="text-sm text-destructive">{error}<Button variant="ghost" onClick={() => { setLocalError(""); importSource.reset(); activate.reset(); revoke.reset(); versions.refetch(); preview.refetch(); }}>Clear error / reload</Button></div> : null}
    {versions.isPending ? <p role="status">Loading source versions...</p> : null}
    <details>
      <summary className="cursor-pointer font-medium">Import a source bundle</summary>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {fields.map(field => <Field key={field.key} label={field.label}>
          <Input type="file" accept={field.accept} disabled={busy} onChange={event => {
            const file = event.target.files?.[0];
            setFiles(current => ({ ...current, [field.key]: file }));
            setLocalError(file && file.size > field.limit ? `${field.label} exceeds ${field.limit / 1024} KB.` : "");
            importSource.reset();
          }} />
        </Field>)}
      </div>
      <p className="my-3 text-sm text-muted-foreground">Use the Markdown experience bank, preferences, and layout sources. The layout is stored for later rendering; it is not compiled here. Files stay in this local app and its private backups.</p>
      <Button disabled={busy || Boolean(localError) || fields.some(field => !files[field.key])} onClick={() => { setNotice(""); importSource.mutate(); }}>
        {importSource.isPending ? "Validating sources..." : "Import and validate"}
      </Button>
    </details>
    {versions.data?.versions.length ? <Field label="Source version">
      <Select value={sourceId} disabled={busy} onChange={event => { setSelected(event.target.value); setReviewedHash(null); setNotice(""); activate.reset(); revoke.reset(); }}>
        {versions.data.versions.map(version => <option key={version.id} value={version.id}>{version.bank_version} — {version.status} — {version.bundle_hash.slice(0, 8)}</option>)}
      </Select>
    </Field> : versions.data ? <p className="text-sm">No sources imported yet.</p> : null}
    {preview.isFetching && sourceId ? <p role="status">Loading source review...</p> : null}
    {source ? <>
      <div className="flex flex-wrap gap-3 text-sm">
        <strong>Source status: {source.status}</strong>
        <span>{source.eligible_count} allowed claims</span><span>{source.excluded_count} excluded claims</span>
      </div>
      <p className="text-sm">Recorded approval: {source.approval.status}{source.approval.approved_at ? ` (${source.approval.approved_at})` : ""}. Activation keeps every exclusion and does not approve a final resume.</p>
      <details><summary className="cursor-pointer font-medium">Identity, education, and records</summary>
        <div className="mt-2 grid gap-2 text-sm">
          <p>{[source.identity.name, source.identity.location, source.identity.email, source.identity.phone, source.identity.website, source.identity.github, source.identity.linkedin].filter(Boolean).join(" · ")}</p>
          {source.education.map(item => <p key={item.id}>{item.institution} · {item.degree} · {item.graduation_display} · {item.gpa} · {item.minors.join(", ")}</p>)}
          {source.records.map(item => <p key={item.id}>{item.employer || item.name} · {item.title_display || item.kind} · {item.dates_display || [item.start, item.end].filter(Boolean).join(" – ") || "Dates not supplied"}</p>)}
        </div>
      </details>
      {[false, true].map(excluded => <details key={String(excluded)} open={excluded}>
        <summary className="cursor-pointer font-medium">{excluded ? "Excluded claims" : "Allowed claims"}</summary>
        <ul className="mt-2 grid gap-3 text-sm">
          {source.claims.filter(claim => source.validation.excluded_claim_ids.includes(claim.id) === excluded).map(claim => <li key={claim.id} className="border-l-2 border-border pl-3">
            <p><strong>{claim.id}</strong> — {claim.text}</p>
            {claim.constraints.map((constraint, i) => <p key={i} className="text-muted-foreground">{constraint}</p>)}
            {claim.confirmation_note ? <p>{claim.confirmation_note}</p> : null}
          </li>)}
        </ul>
      </details>)}
      <details><summary className="cursor-pointer font-medium">Preferences and unresolved fields</summary>
        <p className="mt-2 text-sm">Unknown: {Object.keys(source.unknowns).map(key => key.replaceAll("_", " ")).join(", ") || "None recorded"}. Missing values are not filled in automatically.</p>
        <PreferenceValues value={source.preferences} />
      </details>
      <details><summary className="cursor-pointer font-medium">Layout and validation notes</summary>
        <ul className="my-2 list-disc pl-5 text-sm">{source.validation.warnings.map(warning => <li key={warning}>{warning}</li>)}</ul>
        <p className="break-all text-xs text-muted-foreground">Template: {source.template_hash}<br />Bundle: {source.bundle_hash}</p>
        <details className="mt-2"><summary className="cursor-pointer text-sm">View layout sources</summary>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">{source.template_tex}</pre>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-xs">{source.style_guide}</pre>
        </details>
      </details>
      <details><summary className="cursor-pointer font-medium">Activation history</summary>
        {source.events.length ? <ul className="mt-2 text-sm">{source.events.map(event => <li key={event.sequence}>{event.action} · {event.created_at}</li>)}</ul> : <p className="mt-2 text-sm">Imported, not activated.</p>}
      </details>
      {mayActivate ? <div className="grid gap-3 border-t border-border pt-3">
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={reviewedHash === source.bundle_hash} onChange={event => setReviewedHash(event.target.checked ? source.bundle_hash : null)} />
          I reviewed this version's facts, exclusions, preferences, and layout sources.</label>
        <Button className="justify-self-start" disabled={busy || reviewedHash !== source.bundle_hash || versions.isFetching || preview.isFetching || !versions.data} onClick={() => activate.mutate()}>{activate.isPending ? "Activating..." : "Activate reviewed sources"}</Button>
      </div> : null}
      {source.status === "active" ? <Button className="justify-self-start" variant="secondary" disabled={busy || versions.isFetching || !versions.data} onClick={() => revoke.mutate()}>{revoke.isPending ? "Revoking..." : "Revoke this version"}</Button> : null}
      <p className="text-xs text-muted-foreground">For corrections, import a new source version and review it. Existing versions remain in history.</p>
    </> : null}
  </Panel></div>;
}

function PreferenceValues({ value }: { value: Record<string, unknown> }) {
  return <dl className="my-2 grid gap-2 border-l border-border pl-3 text-sm">{Object.entries(value).map(([key, item]) => <div key={key}>
    <dt className="font-medium">{key.replaceAll("_", " ")}</dt>
    <dd>{item && typeof item === "object" && !Array.isArray(item) ? <PreferenceValues value={item as Record<string, unknown>} /> : Array.isArray(item) ? item.join(", ") : item === null ? "Not specified" : typeof item === "boolean" ? item ? "Yes" : "No" : String(item)}</dd>
  </div>)}</dl>;
}
