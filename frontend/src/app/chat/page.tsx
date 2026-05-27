"use client";

import { MessageSquare, Wrench } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PageHeader, Panel } from "@/components/ui/panel";

export default function ChatPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Chat"
        description="Reserved for the future tool-calling assistant. The current v1 uses explicit forms and AI action buttons."
      />
      <Panel>
        <div className="flex items-start gap-4">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-accent text-accent-foreground">
            <MessageSquare className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold">Assistant route is ready</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              The backend service functions already expose the actions a future agent can call: save jobs, update
              statuses, analyze descriptions, generate resume guidance, practice interviews, and produce study plans.
            </p>
            <div className="mt-5 flex gap-2">
              <Link href="/jobs">
                <Button>
                  <Wrench className="h-4 w-4" />
                  Use tools
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button variant="secondary">Dashboard</Button>
              </Link>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

