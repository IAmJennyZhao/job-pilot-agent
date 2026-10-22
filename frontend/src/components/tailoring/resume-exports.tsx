"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReviewWorkspace, ResumeRenderPreview } from "@/lib/review-types";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";

export function ResumeExports({ view, disabled }: { view: ReviewWorkspace; disabled: boolean }) {
  const cache = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>();
  const [preview, setPreview] = useState<ResumeRenderPreview>();
  const [pdfUrl, setPdfUrl] = useState<string>();
  const [checked, setChecked] = useState(false);
  const [message, setMessage] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const key = ["resume-renders", view.baseline_id, view.revision.id];
  const query = useQuery({ queryKey: key, queryFn: () => api.resumeRenders(view.baseline_id, view.revision.id) });
  const selected = query.data?.find(r => r.id === selectedId) ?? query.data?.[0];
  const clearPreview = () => { setPreview(undefined); setChecked(false); setMessage(""); };
  useEffect(() => { if (disabled) { setPreview(undefined); setChecked(false); } }, [disabled]);
  useEffect(() => {
    if (!preview) { setPdfUrl(undefined); return; }
    const bytes = Uint8Array.from(atob(preview.pdf_base64), c => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    setPdfUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [preview]);
  const render = useMutation({ mutationFn: () => api.renderResume(view.baseline_id, { revision_id: view.revision.id, content_hash: view.revision.content_hash, validation_hash: view.revision.validation_hash, input_hash: view.input_hash }),
    onSuccess: result => { setSelectedId(result.id); clearPreview(); cache.invalidateQueries({ queryKey: key }); } });
  const open = useMutation({ mutationFn: () => api.previewResumeRender(view.baseline_id, selected!.id), onSuccess: result => { setPreview(result); setChecked(false); } });
  const approve = useMutation({ mutationFn: () => api.approveResumeRender(view.baseline_id, selected!.id, { preview_receipt_id: preview!.preview_receipt_id, manifest_hash: preview!.manifest_hash, layout_reviewed: checked }),
    onSuccess: () => { cache.invalidateQueries({ queryKey: key }); setMessage("Final approval saved for these exact PDF, TeX and text files."); } });
  const remove = useMutation({ mutationFn: () => api.deleteResumeRender(view.baseline_id, selected!.id), onSuccess: () => { setSelectedId(undefined); clearPreview(); cache.invalidateQueries({ queryKey: key }); } });
  const busy = disabled || render.isPending || open.isPending || approve.isPending || remove.isPending;
  const download = async (format: "pdf" | "tex" | "txt", copy = false) => {
    setDownloadError(""); setMessage("");
    try {
      const blob = await api.downloadResumeRender(view.baseline_id, selected!.id, format);
      if (copy) { await navigator.clipboard.writeText(await blob.text()); setMessage("Approved export text copied."); return; }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = `resume-${selected!.id.slice(0, 8)}.${format}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setDownloadError(error instanceof Error ? error.message : "Download failed. Please retry."); }
  };
  const error = query.error || render.error || open.error || approve.error || remove.error;
  return <section aria-label="Resume rendering and downloads" className="grid min-w-0 gap-3 rounded border border-border p-4">
    <h4 className="font-medium">PDF preview and final exports</h4>
    <p className="text-sm">Render the saved revision, inspect its layout, then approve the exact files. Page-fit changes must be saved as a new revision.</p>
    {disabled ? <p className="text-sm">Save or discard unsaved edits before previewing or approving exports.</p> : null}
    <Button className="w-fit" variant="secondary" disabled={busy || !view.approval_eligible} onClick={() => { clearPreview(); render.reset(); open.reset(); approve.reset(); remove.reset(); render.mutate(); }}>{render.isPending ? "Rendering PDF…" : "Render saved revision"}</Button>
    {query.isLoading ? <p role="status">Loading saved exports…</p> : null}
    {query.data?.length ? <Field label="Saved render history"><Select value={selected?.id ?? ""} disabled={busy} onChange={e => { setSelectedId(e.target.value); clearPreview(); open.reset(); approve.reset(); remove.reset(); }}>
      {query.data.map(r => <option key={r.id} value={r.id}>{new Date(r.created_at).toLocaleString()} · {r.approved_at ? "Final approved" : r.validation.valid ? "Awaiting layout review" : "Layout needs correction"}</option>)}
    </Select></Field> : <p className="text-sm text-muted-foreground">No PDF has been rendered for this saved revision.</p>}
    {selected ? <>
      <p className="text-sm">{selected.validation.pages} {selected.validation.pages === 1 ? "page" : "pages"} · {selected.approved_at ? "Final approved export" : "Draft preview"}</p>
      {selected.validation.issues.map(issue => <p key={issue} role="alert" className="text-sm text-warning-foreground">{issue}</p>)}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={busy} onClick={() => open.mutate()}>{open.isPending ? "Opening preview…" : "Open PDF preview"}</Button>
        {!selected.approved_at ? <Button variant="ghost" disabled={busy} onClick={() => remove.mutate()}>Remove unapproved preview</Button> : null}
      </div>
      {preview && !disabled ? <div className="grid min-w-0 gap-3">
        <p className="text-sm">Inspect spacing, page fit, links and text. Automated checks cannot guarantee visual quality or factual accuracy.</p>
        {pdfUrl ? <a href={pdfUrl} target="_blank" rel="noreferrer" className="w-fit underline">Open full-size PDF</a> : null}
        {preview.page_images.map((page, i) => <img key={i} src={`data:image/png;base64,${page}`} alt={`Rendered resume page ${i + 1}`} className="h-auto w-full border border-border bg-white" />)}
        {!selected.approved_at ? <>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={checked} disabled={busy} onChange={e => setChecked(e.target.checked)} />I inspected this exact PDF and approve its layout.</label>
          {!view.approved_current ? <p className="text-sm">Use Mark reviewed above to confirm the current content and evidence before final approval.</p> : null}
          <Button className="w-fit" disabled={busy || !checked || !view.approved_current || !selected.validation.valid || preview.manifest_hash !== selected.manifest_hash} onClick={() => approve.mutate()}>Approve final exports</Button>
        </> : null}
      </div> : null}
      {selected.approved_at ? <>
        <p className="text-sm">Approved {new Date(selected.approved_at).toLocaleString()}. Downloads return these saved bytes, including when viewing historical revisions.</p>
        <div className="flex flex-wrap gap-2">{(["pdf", "tex", "txt"] as const).map(format => <Button key={format} variant="secondary" disabled={busy} onClick={() => download(format)}>Download {format === "txt" ? "text" : format === "tex" ? "TeX" : "PDF"}</Button>)}<Button variant="ghost" disabled={busy} onClick={() => download("txt", true)}>Copy approved text</Button></div>
      </> : null}
    </> : null}
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {error || downloadError ? <div role="alert" className="text-sm text-destructive">{error?.message || downloadError}<Button variant="ghost" onClick={() => query.refetch()}>Refresh export history</Button></div> : null}
  </section>;
}
