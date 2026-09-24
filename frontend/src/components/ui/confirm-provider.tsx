"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Dialog } from "./dialog";
import { Button } from "./button";

const ConfirmContext = createContext<(message: string) => Promise<boolean>>(() => Promise.resolve(false));

export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const pending = useRef<((value: boolean) => void) | null>(null);
  const pathname = usePathname();
  const finish = (accepted: boolean) => {
    pending.current?.(accepted);
    pending.current = null;
    setMessage(null);
  };
  useEffect(() => { finish(false); }, [pathname]);
  useEffect(() => () => { pending.current?.(false); }, []);
  const confirm = (text: string) => new Promise<boolean>(resolve => {
    pending.current?.(false);
    pending.current = resolve;
    setMessage(text);
  });
  const action = message?.startsWith("Delete") ? "Delete" : message?.startsWith("Archive") ? "Archive" : message?.startsWith("Clear") ? "Clear draft" : message?.startsWith("Discard") ? "Discard changes" : "Replace draft";
  return <ConfirmContext.Provider value={confirm}>{children}{message ? <Dialog title="Confirm change" onClose={() => finish(false)}>
    <p className="mb-5 text-sm">{message}</p>
    <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => finish(false)}>Cancel</Button><Button variant={action === "Delete" ? "danger" : "primary"} onClick={() => finish(true)}>{action}</Button></div>
  </Dialog> : null}</ConfirmContext.Provider>;
}

export const useConfirm = () => useContext(ConfirmContext);
