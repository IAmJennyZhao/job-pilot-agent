"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { InterviewScoreEntry } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { formatDate } from "@/lib/utils";

export function AttemptHistory({ questionId, onRevise, disabled }: { questionId: string; onRevise?: (answer: string) => void; disabled?: boolean }) {
  const query = useQuery({ queryKey: ["interview-attempts", questionId], queryFn: () => api.questionAttempts(questionId) });
  const [selected, setSelected] = useState("");
  const attempts = query.data ?? [];
  const previous = attempts.find(item => item.message_id === selected) ?? attempts[0];
  const latest = attempts.at(-1);
  return <section className="rounded-md border border-border p-4"><h3 className="font-semibold">Answer attempts ({attempts.length})</h3>
    <p className="my-2 text-xs text-muted-foreground">Saved answers to this exact question across sessions. Scores are AI coaching estimates; compare the feedback as well as the number.</p>
    {query.isLoading ? <p>Loading attempts…</p> : query.error ? <><p role="alert">{query.error.message}</p><Button onClick={() => query.refetch()}>Retry attempts</Button></> : !latest ? <p className="text-sm">Evaluate an answer to save your first attempt.</p> : <>
      {attempts.length > 1 ? <><label className="mb-3 grid gap-1 text-sm">Compare with<Select value={previous.message_id} onChange={event => setSelected(event.target.value)}>{attempts.slice(0, -1).map((item, index) => <option key={item.message_id} value={item.message_id}>Attempt {index + 1} · {formatDate(item.created_at)} · {item.score}/100</option>)}</Select></label>
        <p className="mb-3 text-sm">Score change: {latest.score - previous.score > 0 ? "+" : ""}{latest.score - previous.score} points from selected attempt to latest.</p></> : null}
      <div className="grid gap-3 md:grid-cols-2">{attempts.length > 1 ? <Attempt item={previous} title="Earlier attempt" onRevise={onRevise} disabled={disabled} /> : null}<Attempt item={latest} title="Latest attempt" onRevise={onRevise} disabled={disabled} /></div>
    </>}
  </section>;
}

function Attempt({ item, title, onRevise, disabled }: { item: InterviewScoreEntry; title: string; onRevise?: (answer: string) => void; disabled?: boolean }) {
  const feedback = item.feedback ?? {};
  const elapsed = feedback.elapsed_seconds;
  const limit = feedback.time_limit_seconds;
  return <div className="min-w-0 rounded border border-border p-3 text-sm"><h4 className="font-medium">{title} · {item.score}/100</h4><p className="text-xs text-muted-foreground">{formatDate(item.created_at)}{typeof elapsed === "number" ? ` · ${elapsed}s${typeof limit === "number" ? ` / ${limit}s target` : ""}` : " · Untimed"}</p>
    <p className="my-3 whitespace-pre-wrap break-words">{item.answer ?? "Answer unavailable for this older attempt."}</p>
    {(["what_went_well", "what_was_missing", "coaching_notes"] as const).map(key => Array.isArray(feedback[key]) && (feedback[key] as unknown[]).length ? <div key={key} className="my-2"><h5 className="font-medium">{key.replaceAll("_", " ")}</h5><ul className="list-inside list-disc">{(feedback[key] as unknown[]).map((value, index) => <li key={index}>{String(value)}</li>)}</ul></div> : null)}
    {onRevise && item.answer ? <Button disabled={disabled} variant="secondary" onClick={() => onRevise(item.answer!)}>Revise this answer</Button> : null}
  </div>;
}
