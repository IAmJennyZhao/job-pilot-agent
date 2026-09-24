"use client";

import { Button } from "./button";
import { Input } from "./field";

/** Keep item boundaries explicit: punctuation is always content. */
export function ListEditor({ label, value, onChange }: { label: string; value: string[]; onChange: (value: string[]) => void }) {
  return <fieldset className="grid min-w-0 gap-2">
    <legend className="mb-2 text-sm font-medium">{label}</legend>
    {value.map((item, index) => <div key={index} className="flex gap-2">
      <Input aria-label={`${label} item ${index + 1}`} value={item} onChange={event => onChange(value.map((old, i) => i === index ? event.target.value : old))} />
      <Button variant="ghost" aria-label={`Remove ${label.toLowerCase()} item ${index + 1}`} onClick={() => onChange(value.filter((_, i) => i !== index))}>Remove</Button>
    </div>)}
    <Button className="justify-self-start" variant="secondary" onClick={() => onChange([...value, ""])}>Add item</Button>
  </fieldset>;
}
