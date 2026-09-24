type EditableJob = { pay_min?: number | null; pay_max?: number | null; links?: { url: string }[] };

export function validateJobFields(job: EditableJob): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const key of ["pay_min", "pay_max"] as const) {
    const value = job[key];
    if (value != null && (!Number.isFinite(value) || value < 0)) errors[key] = "Enter zero or a positive amount.";
  }
  if (job.pay_min != null && job.pay_max != null && job.pay_min > job.pay_max) errors.pay_max = "Maximum pay must be at least the minimum.";
  job.links?.forEach((link, index) => {
    if (!link.url.trim()) return;
    try {
      if (!["http:", "https:"].includes(new URL(link.url).protocol)) throw new Error();
    } catch { errors[`link_${index}`] = "Enter a complete http:// or https:// link."; }
  });
  return errors;
}
