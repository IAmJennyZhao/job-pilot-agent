"use client";

import { Button } from "@/components/ui/button";

export function DraftRecovery({ name, draft }: { name: string; draft: { recoveryRaw: string | null; discard: () => void; storageError: boolean } }) {
  return <>
    {draft.recoveryRaw !== null ? <div role="alert" className="grid gap-2 text-sm">
      <p>The saved {name} has an incompatible format. Download a recovery copy before discarding it.</p>
      <a className="underline" href={`data:application/json;charset=utf-8,${encodeURIComponent(draft.recoveryRaw)}`} download={`${name.replaceAll(" ", "-")}-recovery.json`}>Download {name} recovery</a>
      <Button variant="ghost" className="w-fit" onClick={draft.discard}>Discard incompatible {name}</Button>
    </div> : null}
    {draft.storageError ? <p role="alert" className="text-sm text-warning-foreground">Browser storage is unavailable for {name}. Keep this tab open and copy unsaved work before leaving.</p> : null}
  </>;
}
