"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Select } from "@/components/ui/field";

/** Presentation only: collapsing preparation never unmounts its editors or requests. */
export function usePreparationDisclosure(hasDraft: boolean, needsAttention: boolean, anchor: string) {
  const [open, setOpen] = useState(true);
  const seenDraft = useRef(false);
  useEffect(() => {
    // Apply the compact default once. Query refreshes must not close an editor
    // the user deliberately reopened, including after saving a description.
    if (hasDraft && !seenDraft.current) {
      setOpen(needsAttention || window.location.hash === `#${anchor}`);
      seenDraft.current = true;
    }
    if (needsAttention) setOpen(true);
  }, [hasDraft, needsAttention, anchor]);
  useEffect(() => {
    const reveal = () => { if (window.location.hash === `#${anchor}`) setOpen(true); };
    window.addEventListener("hashchange", reveal);
    return () => window.removeEventListener("hashchange", reveal);
  }, [anchor]);
  return { open, setOpen };
}

export function DocumentWorkflowSteps({ kind, preparationId, hasDraft, onPrepare }: {
  kind: "resume" | "letter"; preparationId: string; hasDraft: boolean; onPrepare: () => void;
}) {
  const steps = [
    { label: "Preparation", id: preparationId },
    { label: "Generation", id: `${kind}-history` },
    { label: "Review / edit", id: `${kind}-review` },
    { label: "Export", id: `${kind}-exports` }
  ];
  return <nav aria-label={kind === "resume" ? "Resume workflow" : "Cover letter workflow"} className="rounded-md border border-border bg-muted/30 p-2">
    <ol className="grid grid-cols-2 gap-1 sm:grid-cols-4">{steps.map((step, index) => <li key={step.id}>
      <Button variant="ghost" className="w-full justify-start text-left" disabled={index > 1 && !hasDraft} onClick={() => {
        if (index === 0) onPrepare();
        requestAnimationFrame(() => {
          const target = document.getElementById(step.id);
          target?.scrollIntoView({ block: "start", behavior: "smooth" });
          target?.focus({ preventScroll: true });
        });
      }}><span className="text-xs text-muted-foreground" aria-hidden="true">{index + 1}</span>{step.label}</Button>
    </li>)}</ol>
  </nav>;
}

export function SavedTextPreview({ kind, text, revision, historical, unsaved }: {
  kind: "resume" | "letter"; text: string; revision: string; historical: boolean; unsaved: boolean;
}) {
  const [large, setLarge] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const title = kind === "resume" ? "Saved resume text preview" : "Saved letter text preview";
  return <section aria-label={title} className="grid min-w-0 gap-3 rounded-md border border-border bg-background p-4" data-preview-state="saved">
    <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-medium">{kind === "resume" ? historical ? "Historical resume text" : "Last saved resume text" : "Saved letter preview"}</h4><Badge>{historical ? "Historical saved version" : "Saved content"}</Badge></div>
    <p className="text-xs text-muted-foreground">{revision}. {unsaved ? "Your unsaved local edits are not shown here. Save a revision to update this preview." : "This preview reflects the selected saved revision."}</p>
    <div className="flex flex-wrap items-end gap-2"><Field label={`Saved ${kind} text size`}><Select value={large ? "large" : "standard"} onChange={event => setLarge(event.target.value === "large")}><option value="standard">Standard text</option><option value="large">Larger text</option></Select></Field><Button variant="secondary" onClick={() => setExpanded(true)}>Open larger text preview</Button></div>
    <pre tabIndex={0} aria-label={kind === "resume" ? "Resume draft preview" : "Saved letter prose"} className={`max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded border border-border bg-card p-4 font-sans leading-relaxed ${large ? "text-base" : "text-sm"}`}>{text}</pre>
    {expanded ? <Dialog title={title} onClose={() => setExpanded(false)}><p className="mb-3 text-xs text-muted-foreground">{revision}. Last saved content{unsaved ? "; unsaved local edits are not included" : ""}.</p><pre aria-label={`Expanded saved ${kind} text`} className="whitespace-pre-wrap break-words font-sans text-base leading-relaxed">{text}</pre></Dialog> : null}
  </section>;
}
