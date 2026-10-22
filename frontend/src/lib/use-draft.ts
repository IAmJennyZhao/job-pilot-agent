"use client";

import { useEffect, useRef, useState } from "react";

/** Per-record durable browser drafts survive remounts without leaking edits between records. */
export function useDraft<T>(key: string, initial: T) {
  const storageKey = `job-pilot:draft:${key}`;
  const initialJson = JSON.stringify(initial);
  const persisted = useRef<{ key: string; value: string | null }>({ key: storageKey, value: null });
  const [state, setState] = useState({ key: storageKey, value: initial, dirty: false, ready: false, base: initialJson });
  const [storageError, setStorageError] = useState(false);
  useEffect(() => {
    let value = JSON.parse(initialJson) as T;
    let dirty = false;
    try {
      // Each tab keeps its own recovery copy. The shared copy also supports
      // recovery in a newly opened tab or browser session.
      const saved = sessionStorage.getItem(storageKey) ?? localStorage.getItem(storageKey);
      if (saved !== null) { value = JSON.parse(saved) as T; dirty = true; }
      persisted.current = { key: storageKey, value: saved };
    } catch { setStorageError(true); }
    setState({ key: storageKey, value, dirty, ready: true, base: initialJson });
    // Hydrate only when the identity changes; server updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);
  useEffect(() => {
    setState(current => current.key === storageKey && current.base !== initialJson
      ? { ...current, base: initialJson, value: current.dirty ? current.value : JSON.parse(initialJson) as T }
      : current);
  }, [initialJson, storageKey]);
  useEffect(() => {
    if (!state.ready || state.key !== storageKey) return;
    try {
      if (state.dirty) {
        const serialized = JSON.stringify(state.value);
        sessionStorage.setItem(storageKey, serialized);
        localStorage.setItem(storageKey, serialized);
        persisted.current = { key: storageKey, value: serialized };
      } else {
        sessionStorage.removeItem(storageKey);
        if (persisted.current.key === storageKey && persisted.current.value !== null && localStorage.getItem(storageKey) === persisted.current.value) localStorage.removeItem(storageKey);
        persisted.current = { key: storageKey, value: null };
      }
    } catch { setStorageError(true); }
  }, [state, storageKey]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (state.dirty && storageError) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state.dirty, storageError]);
  const update: React.Dispatch<React.SetStateAction<T>> = next => {
    setState(current => {
      const value = current.key === storageKey ? current.value : initial;
      return { ...current, key: storageKey, value: typeof next === "function" ? (next as (value: T) => T)(value) : next, dirty: true };
    });
  };
  const clear = () => {
    setState(current => ({ ...current, dirty: false }));
    try {
      sessionStorage.removeItem(storageKey);
      if (persisted.current.key === storageKey && persisted.current.value !== null && localStorage.getItem(storageKey) === persisted.current.value) localStorage.removeItem(storageKey);
      persisted.current = { key: storageKey, value: null };
    } catch { setStorageError(true); }
  };
  const discard = () => {
    clear();
    setState(current => ({ ...current, value: JSON.parse(initialJson) as T, dirty: false, base: initialJson }));
  };
  return { value: state.key === storageKey ? state.value : initial, setValue: update, clear, discard, dirty: state.key === storageKey && state.dirty, ready: state.key === storageKey && state.ready, storageError };
}
