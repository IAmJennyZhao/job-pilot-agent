"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Button } from "./button";
import { useViewActive } from "@/components/layout/retained-view";

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const viewActive = useViewActive();
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => { if (!viewActive) close.current(); }, [viewActive]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      requestAnimationFrame(() => { if (previous?.isConnected) previous.focus(); });
    };
  }, []);
  return createPortal(<dialog ref={ref} aria-label={title} onCancel={event => { event.preventDefault(); close.current(); }} onClick={event => { if (event.target !== ref.current) return; const bounds = event.currentTarget.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close.current(); }} className="m-auto max-h-[90dvh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-lg border border-border bg-popover p-5 text-popover-foreground shadow-xl backdrop:bg-black/40">
    <div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-semibold">{title}</h2><Button variant="ghost" onClick={onClose} aria-label={`Close ${title}`}>Close</Button></div>
    {children}
  </dialog>, document.body);
}
