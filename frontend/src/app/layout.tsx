import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerPilot Agent",
  description: "AI job search dashboard for tracking applications and skill gaps."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}

