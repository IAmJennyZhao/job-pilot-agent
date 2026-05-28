"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Save, UserRound } from "lucide-react";
import * as React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Badge, PageHeader, Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { ResumeProfile } from "@/lib/types";
import { csvToList, listToCsv } from "@/lib/utils";

const profileSchema = z.object({
  name: z.string().optional(),
  target_roles: z.string().optional(),
  summary: z.string().optional(),
  skills: z.string().optional(),
  certifications: z.string().optional(),
  resume_text: z.string().optional()
});

type ProfileForm = z.infer<typeof profileSchema>;

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const { data: profile, isLoading, error } = useQuery({ queryKey: ["profile"], queryFn: api.profile });
  const form = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: "",
      target_roles: "",
      summary: "",
      skills: "",
      certifications: "",
      resume_text: ""
    }
  });

  React.useEffect(() => {
    if (profile) {
      form.reset({
        name: profile.name ?? "",
        target_roles: listToCsv(profile.target_roles),
        summary: profile.summary ?? "",
        skills: listToCsv(profile.skills),
        certifications: listToCsv(profile.certifications),
        resume_text: profile.resume_text
      });
    }
  }, [form, profile]);

  const mutation = useMutation({
    mutationFn: (values: ProfileForm) => {
      const payload = {
        name: values.name || null,
        target_roles: csvToList(values.target_roles ?? ""),
        summary: values.summary || null,
        skills: csvToList(values.skills ?? ""),
        certifications: csvToList(values.certifications ?? ""),
        resume_text: values.resume_text ?? "",
        projects: profile?.projects ?? [],
        experience: profile?.experience ?? [],
        education: profile?.education ?? []
      };
      return profile ? api.updateProfile(profile.id, payload) : api.saveProfile(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Resume Profile"
        description="Maintain the single active profile used for job matching, resume suggestions, interview questions, and study plans."
      />
      {error ? <Panel className="border-rose-200 bg-rose-50 text-sm text-rose-700">{(error as Error).message}</Panel> : null}
      {isLoading ? <Panel>Loading profile...</Panel> : null}

      <ProfileReadinessPanel profile={profile ?? null} />

      <Panel>
        <div className="mb-5 flex items-center gap-2">
          <UserRound className="h-4 w-4 text-primary" />
          <h2 className="text-base font-semibold">{profile ? "Active Profile" : "Create Active Profile"}</h2>
        </div>
        <form className="grid gap-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Name">
              <Input {...form.register("name")} />
            </Field>
            <Field label="Target roles">
              <Input {...form.register("target_roles")} placeholder="Applied AI Engineer, AI Software Engineer" />
            </Field>
          </div>
          <Field label="Summary">
            <Textarea {...form.register("summary")} />
          </Field>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="Skills">
              <Textarea {...form.register("skills")} placeholder="Python, FastAPI, React, RAG" />
            </Field>
            <Field label="Certifications">
              <Textarea {...form.register("certifications")} placeholder="OpenAI API projects, AWS..." />
            </Field>
          </div>
          <Field label="Resume text">
            <Textarea {...form.register("resume_text")} className="min-h-72" />
          </Field>
          {mutation.error ? <p className="text-sm text-destructive">{(mutation.error as Error).message}</p> : null}
          <Button type="submit" disabled={mutation.isPending}>
            <Save className="h-4 w-4" />
            {mutation.isPending ? "Saving..." : "Save profile"}
          </Button>
        </form>
      </Panel>
    </div>
  );
}

function ProfileReadinessPanel({ profile }: { profile: ResumeProfile | null }) {
  const checks = [
    { label: "Active profile", ready: Boolean(profile) },
    { label: "Resume text", ready: Boolean(profile?.resume_text.trim()) },
    { label: "Skills", ready: Boolean(profile?.skills.length) }
  ];
  const ready = checks.every((item) => item.ready);

  return (
    <Panel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Matching Readiness</h2>
          <p className="mt-1 text-sm text-muted-foreground">Job Intelligence uses this profile for fit scores and resume suggestions.</p>
        </div>
        <Badge tone={ready ? "good" : "warn"}>{ready ? "Ready" : "Needs profile"}</Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {checks.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-sm">
            {item.ready ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertCircle className="h-4 w-4 text-amber-600" />}
            {item.label}
          </div>
        ))}
      </div>
    </Panel>
  );
}
