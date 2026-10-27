import type { DashboardActionSuggestion, JobAction } from "@/lib/types";

export const actionViews = ["To do", "Today", "Overdue", "Upcoming", "Suggestions", "Completed"] as const;
export type ActionView = typeof actionViews[number];
export type AgendaItem = {
  id: string;
  action?: JobAction;
  suggestion?: DashboardActionSuggestion;
};

export function agendaMatches(item: AgendaItem, view: ActionView, today: string) {
  const pending = item.action && !item.action.completed_at;
  switch (view) {
    case "To do": return Boolean(pending || item.suggestion);
    case "Today": return Boolean(pending && item.action?.due_date === today);
    case "Overdue": return Boolean(pending && item.action!.due_date < today);
    case "Upcoming": return Boolean(pending && item.action!.due_date > today);
    case "Completed": return Boolean(item.action?.completed_at);
    case "Suggestions": return Boolean(item.suggestion);
  }
}

/** Presentation only: dates and suggestion eligibility come from their existing owners. */
export function mergeAgenda(actions: JobAction[], suggestions: DashboardActionSuggestion[], today: string): AgendaItem[] {
  const jobs = new Map<string, AgendaItem>();
  for (const action of actions) jobs.set(action.job_id, { id: action.job_id, action });
  for (const suggestion of suggestions) {
    // Missing analysis belongs to coverage/review, rather than the action queue.
    const reasons = suggestion.reasons.filter(reason => reason.kind !== "analysis");
    if (reasons.length) jobs.set(suggestion.id, { ...jobs.get(suggestion.id), id: suggestion.id, suggestion: { ...suggestion, reasons } });
  }
  const priority = (item: AgendaItem) => {
    if (item.action && !item.action.completed_at && item.action.due_date <= today) return 0;
    if (item.suggestion?.reasons.some(reason => reason.kind === "stale")) return 1;
    if (item.suggestion) return 2;
    return item.action?.completed_at ? 4 : 3;
  };
  return [...jobs.values()].sort((a, b) => priority(a) - priority(b)
    || (a.action?.due_date ?? "9999").localeCompare(b.action?.due_date ?? "9999")
    || (a.suggestion?.last_movement_at ?? "").localeCompare(b.suggestion?.last_movement_at ?? "")
    || a.id.localeCompare(b.id));
}
