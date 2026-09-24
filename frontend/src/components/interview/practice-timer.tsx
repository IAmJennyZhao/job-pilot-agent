"use client";

import { useEffect, useState } from "react";
import { useDraft } from "@/lib/use-draft";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";

export function usePracticeTimer(key: string) {
  const draft = useDraft<{ started: number | null; elapsed: number; limit: number }>(`timer:${key}`, { started: null, elapsed: 0, limit: 120 });
  const [now, setNow] = useState(Date.now);
  useEffect(() => { const id = window.setInterval(() => setNow(Date.now()), 500); return () => window.clearInterval(id); }, []);
  const elapsed = () => Math.min(604800, Math.floor((draft.value.elapsed + (draft.value.started === null ? 0 : Math.max(0, Date.now() - draft.value.started))) / 1000));
  const stop = () => { const seconds = elapsed(); draft.setValue(current => ({ ...current, started: null, elapsed: seconds * 1000 })); return seconds; };
  const seconds = Math.min(604800, Math.floor((draft.value.elapsed + (draft.value.started === null ? 0 : Math.max(0, now - draft.value.started))) / 1000));
  return { seconds, limit: draft.value.limit, running: draft.value.started !== null, ready: draft.ready, elapsed, stop,
    start: () => { setNow(Date.now()); draft.setValue(current => ({ ...current, started: Date.now() })); },
    reset: () => draft.setValue(current => ({ ...current, started: null, elapsed: 0 })),
    setLimit: (limit: number) => draft.setValue(current => ({ ...current, limit })) };
}

export function PracticeTimer({ timer, disabled }: { timer: ReturnType<typeof usePracticeTimer>; disabled: boolean }) {
  return <div className="rounded-md border border-border p-3">
    <div className="flex flex-wrap items-center gap-3">
      <span className="font-medium" role="timer" aria-label="Answer elapsed time">{Math.floor(timer.seconds / 60)}:{String(timer.seconds % 60).padStart(2, "0")}</span>
      <label className="flex items-center gap-2 text-sm">Answer target<Select aria-label="Answer time target" disabled={disabled || timer.running} value={timer.limit} onChange={event => timer.setLimit(Number(event.target.value))}>{[60, 120, 180, 300, 600].map(value => <option key={value} value={value}>{value / 60} minutes</option>)}</Select></label>
      <Button variant="secondary" disabled={disabled || !timer.ready} onClick={timer.running ? timer.stop : timer.start}>{timer.running ? "Pause timer" : "Start timer"}</Button>
      <Button variant="ghost" disabled={disabled} onClick={timer.reset}>Reset timer</Button>
    </div>
    <p className="mt-2 text-xs text-muted-foreground">The timer keeps running across refreshes until paused. Reaching the target never submits your answer.</p>
    {timer.seconds >= timer.limit ? <p role="status" className="mt-2 text-sm text-warning-foreground">Time target reached. Finish your thought, then evaluate when ready.</p> : null}
  </div>;
}
