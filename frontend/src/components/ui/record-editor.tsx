"use client";

import { Button } from "./button";
import { Field, Input, Textarea } from "./field";

const label = (key: string) => key.replaceAll("_", " ").replace(/^./, c => c.toUpperCase());

function ValueEditor({ name, value, onChange }: { name: string; value: unknown; onChange: (value: unknown) => void }) {
  if (Array.isArray(value)) return <fieldset className="grid gap-2 rounded border border-border p-3"><legend>{name}</legend>{value.map((item, index) => <div key={index} className="grid gap-2"><ValueEditor name={`${name} ${index + 1}`} value={item} onChange={next => onChange(value.map((old, i) => i === index ? next : old))} /><Button variant="ghost" size="sm" onClick={() => onChange(value.filter((_, i) => i !== index))}>Remove {name.toLowerCase()} {index + 1}</Button></div>)}<Button variant="secondary" size="sm" onClick={() => onChange([...value, ""])}>Add {name.toLowerCase()}</Button></fieldset>;
  if (value && typeof value === "object") return <div className="grid gap-3">{Object.entries(value).map(([key, item]) => <ValueEditor key={key} name={label(key)} value={item} onChange={next => onChange({ ...value, [key]: next })} />)}</div>;
  if (typeof value === "boolean") return <label className="flex gap-2"><input type="checkbox" checked={value} onChange={event => onChange(event.target.checked)} />{name}</label>;
  if (typeof value === "number") return <Field label={name}><Input type="number" value={value} onChange={event => onChange(event.target.value === "" ? null : Number(event.target.value))} /></Field>;
  return <Field label={name}><Textarea value={String(value ?? "")} onChange={event => onChange(event.target.value)} /></Field>;
}

export function RecordEditor({ title, value, onChange }: { title: "Experience" | "Projects" | "Education"; value: string; onChange: (value: string) => void }) {
  let records: Record<string, unknown>[];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed) || parsed.some(item => !item || typeof item !== "object" || Array.isArray(item))) throw new Error();
    records = parsed;
  } catch {
    return <Field label={`${title} - recover draft`} error="This older draft contains invalid structured data. Correct it before saving."><Textarea value={value} onChange={event => onChange(event.target.value)} /></Field>;
  }
  const write = (next: Record<string, unknown>[]) => onChange(JSON.stringify(next, null, 2));
  const blank = title === "Experience" ? { company: "", role: "", dates: "", highlights: [""] } : title === "Projects" ? { name: "", description: "", technologies: [""], highlights: [""] } : { institution: "", degree: "", dates: "" };
  return <fieldset className="grid min-w-0 gap-3"><legend className="mb-2 font-semibold">{title}</legend>{records.map((record, index) => <div key={index} className="grid gap-3 rounded border border-border p-3"><ValueEditor name={`${title} ${index + 1}`} value={record} onChange={next => write(records.map((old, i) => i === index ? next as Record<string, unknown> : old))} /><Button variant="ghost" onClick={() => write(records.filter((_, i) => i !== index))}>Remove {title.toLowerCase()} {index + 1}</Button></div>)}<Button variant="secondary" onClick={() => write([...records, blank])}>Add {title.toLowerCase()}</Button></fieldset>;
}
