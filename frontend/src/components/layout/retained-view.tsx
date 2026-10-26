"use client";

import * as React from "react";

const ViewActiveContext = React.createContext(true);

export function useViewActive() {
  return React.useContext(ViewActiveContext);
}

/** A visited workspace stays mounted so tab changes keep transient editor state. */
export function RetainedView({ active, label, children }: { active: boolean; label?: string; children: React.ReactNode }) {
  const [visited, setVisited] = React.useState(active);
  React.useEffect(() => {
    if (active) setVisited(true);
  }, [active]);

  if (!active && !visited) return null;
  return (
    <ViewActiveContext.Provider value={active}>
      <section hidden={!active} inert={!active} aria-hidden={!active} aria-label={label} className="min-w-0">
        {children}
      </section>
    </ViewActiveContext.Provider>
  );
}
