"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 20_000,
            retry: 1
          }
        }
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

