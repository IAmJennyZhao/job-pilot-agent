"use client";

import * as React from "react";

const ViewActiveContext = React.createContext(true);

export function useViewActive() {
  return React.useContext(ViewActiveContext);
}

/** A visited workspace stays mounted so tab changes keep transient editor state. */
export function RetainedView({ active, children }: { active: boolean; children: React.ReactNode }) {
  const [visited, setVisited] = React.useState(active);
  React.useEffect(() => {
    if (active) setVisited(true);
  }, [active]);

  if (!active && !visited) return null;
  return (
    <ViewActiveContext.Provider value={active}>
      <section hidden={!active} inert={!active} aria-hidden={!active} className="min-w-0">
        {children}
      </section>
    </ViewActiveContext.Provider>
  );
}
