"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { PageHeader, Panel } from "@/components/ui/panel";

export default function DataPage() {
  const [file, setFile] = useState<File | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const download = useMutation({ mutationFn: async (path: "backup" | "jobs.csv" | `recovery/${string}`) => {
    const blob = await api.downloadData(path);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = path === "jobs.csv" ? "job-pilot-jobs.csv" : path === "backup" ? "job-pilot-backup.json" : "job-pilot-before-restore.json"; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 10000);
    if (path !== "jobs.csv") {
      const archive = JSON.parse(await blob.text());
      setMessage(archive.missing_files?.length ? `Backup downloaded, but these original PDFs were unavailable: ${archive.missing_files.join(", ")}. Their saved text and records are included.` : "Backup downloaded with all available saved records and resume PDFs.");
    } else setMessage("Jobs CSV downloaded.");
  }});
  const preview = useMutation({ mutationFn: () => { if (!file) throw new Error("Choose a backup file"); return api.previewRestore(file); } });
  const restore = useMutation({ mutationFn: () => { if (!file || !preview.data) throw new Error("Preview the backup first"); return api.restoreData(file, preview.data.sha256, confirmation); }, onSuccess: () => {
    // Old browser drafts must not overwrite restored records with the same IDs.
    for (const storage of [localStorage, sessionStorage]) { for (const key of Object.keys(storage)) { if (key.startsWith("job-pilot:draft:")) storage.removeItem(key); } }
    client.removeQueries(); setConfirmation("");
  }});
  const busy = download.isPending || preview.isPending || restore.isPending;
  return <div className="grid gap-6"><PageHeader title="Export & backups" description="Keep a portable copy of your job search and restore it when needed." />
    <Panel><h2 className="font-semibold">Download your data</h2><p className="my-3 text-sm text-muted-foreground">The JSON backup includes saved jobs, profiles, resumes and PDFs, cover letters, analyses, actions, interview attempts, study plans, and reporting labels. API keys, settings, and unsaved browser drafts are excluded. Maximum archive size: 50 MB. Keep backups private: they contain your career data.</p><div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={() => download.mutate("backup")}>Download full backup</Button><Button disabled={busy} variant="secondary" onClick={() => download.mutate("jobs.csv")}>Export jobs CSV</Button></div>{message ? <p role="status" className="mt-3 text-sm">{message}</p> : null}</Panel>
    <Panel><h2 className="font-semibold">Restore a backup</h2><p className="my-3 text-sm text-muted-foreground">Preview a Job Pilot JSON backup before restoring. Restore replaces all saved data and clears this browser’s unsaved drafts. A recovery copy of the current saved data is kept on this computer before replacement. CSV files cannot be restored.</p>
      <Field label="Backup file"><Input type="file" accept=".json,application/json" disabled={busy} onChange={event => { setFile(event.target.files?.[0] ?? null); preview.reset(); restore.reset(); setConfirmation(""); }} /></Field>
      <Button className="mt-3" variant="secondary" disabled={busy || !file} onClick={() => preview.mutate()}>{preview.isPending ? "Checking backup…" : "Preview backup"}</Button>
      {preview.data && !restore.isSuccess ? <div className="mt-4 grid gap-3"><h3 className="font-medium">Backup contents</h3><dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">{Object.entries(preview.data.counts).map(([name, count]) => <div key={name}><dt className="text-muted-foreground">{name.replaceAll("_", " ")}</dt><dd>{count}</dd></div>)}</dl><p className="text-sm">{preview.data.files} PDF attachments.</p>{preview.data.missing_files.length ? <p role="alert" className="text-sm text-warning-foreground">Missing original PDFs: {preview.data.missing_files.join(", ")}. Only their saved records and text will be restored.</p> : null}<Field label="Type RESTORE to replace all saved data"><Input disabled={busy} value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="off" /></Field><Button variant="danger" disabled={busy || confirmation !== "RESTORE"} onClick={() => restore.mutate()}>{restore.isPending ? "Restoring…" : "Replace data with this backup"}</Button></div> : null}
      {restore.data ? <div role="status" className="mt-4"><p>Restore complete. Your restored data is ready.</p><Button className="mt-2" variant="secondary" disabled={busy} onClick={() => download.mutate(`recovery/${restore.data.recovery_id}`)}>Download pre-restore recovery backup</Button></div> : null}
    </Panel>
    {[download.error, preview.error, restore.error].map((error, index) => error ? <p key={index} role="alert" className="text-sm text-destructive">{error.message}</p> : null)}
  </div>;
}
