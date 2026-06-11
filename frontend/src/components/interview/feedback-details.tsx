import { Badge } from "@/components/ui/panel";
import type { InterviewFeedback } from "@/lib/types";

export const weakPointLabels: Record<string, string> = {
  technical_depth: "Technical depth",
  answer_structure: "Answer structure",
  specific_evidence: "Specific evidence",
  role_alignment: "Role alignment",
  concision: "Concision",
  communication_clarity: "Clarity",
  missing_skill: "Missing skill",
  company_context: "Company context",
  resume_positioning: "Resume positioning"
};

export function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-3">
      <h4 className="font-medium">{title}</h4>
      <ul className="mt-1 list-inside list-disc text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function FeedbackDetails({ feedback }: { feedback: InterviewFeedback }) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="font-semibold">Feedback</h3>
        <Badge tone={feedback.score >= 75 ? "good" : feedback.score >= 50 ? "warn" : "bad"}>Score {feedback.score}</Badge>
      </div>
      <List title="What worked" items={feedback.what_went_well} />
      <List title="What was missing" items={feedback.what_was_missing} />
      <List title="Coaching notes" items={feedback.coaching_notes} />
      <List title="Evidence to add" items={feedback.evidence_to_add} />
      {feedback.weak_point_tags.length ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {feedback.weak_point_tags.map((tag) => (
            <Badge key={tag} tone="warn">
              {weakPointLabels[tag] ?? tag.replace("_", " ")}
            </Badge>
          ))}
        </div>
      ) : null}
      <div className="mt-3">
        <h4 className="font-medium">Stronger answer</h4>
        <p className="mt-1 leading-6 text-muted-foreground">{feedback.suggested_better_answer}</p>
      </div>
    </div>
  );
}
