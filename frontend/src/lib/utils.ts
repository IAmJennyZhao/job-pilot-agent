import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function csvToList(value: string) {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function listToCsv(value: string[] | undefined) {
  return value?.join(", ") ?? "";
}

export function linesToList(value: string) {
  return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
}

export function listToLines(value: string[] | undefined) {
  return value?.join("\n") ?? "";
}

