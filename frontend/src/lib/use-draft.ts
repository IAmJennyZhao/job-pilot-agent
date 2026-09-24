"use client";

import { useEffect, useRef, useState } from "react";

/** Session drafts survive tab switches and reloads without overwriting server updates. */
export function useDraft<T>(key: string, initial: T) {
  const [value, setValue] = useState(initial);
  const [ready, setReady] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const [dirty, setDirty] = useState(false);
  const baseline = useRef(JSON.stringify(initial));
  const storageKey = `job-pilot:draft:${key}`;
  const initialJson = JSON.stringify(initial);
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) { setValue(JSON.parse(saved) as T); setDirty(true); }
    } catch { setStorageError(true); }
    setReady(true);
  }, [storageKey]);
  useEffect(() => {
    if (baseline.current !== initialJson) {
      baseline.current = initialJson;
      if (!dirty) setValue(JSON.parse(initialJson) as T);
    }
  }, [initialJson, dirty]);
  useEffect(() => {
    if (!ready) return;
    try {
      if (dirty) sessionStorage.setItem(storageKey, JSON.stringify(value));
      else sessionStorage.removeItem(storageKey);
    } catch { setStorageError(true); }
  }, [value, dirty, ready, storageKey]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty && storageError) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, storageError]);
  const update: React.Dispatch<React.SetStateAction<T>> = next => {
    setValue(current => typeof next === "function" ? (next as (value: T) => T)(current) : next);
    setDirty(true);
  };
  const clear = () => {
    setDirty(false);
    try { sessionStorage.removeItem(storageKey); } catch { setStorageError(true); }
  };
  return { value, setValue: update, clear, dirty, ready, storageError };
}
