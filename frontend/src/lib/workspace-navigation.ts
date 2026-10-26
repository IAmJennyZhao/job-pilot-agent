/** Keep unrelated search parameters when a user changes a local view. */
export function selectLocalView<T extends string>(
  params: Pick<URLSearchParams, "get">,
  allowed: readonly T[],
  fallback: T
): T {
  const requested = params.get("tab");
  return allowed.find((tab) => tab === requested) ?? fallback;
}

export function localViewHref(pathname: string, params: Pick<URLSearchParams, "toString">, tab: string, hash = "") {
  const next = new URLSearchParams(params.toString());
  next.set("tab", tab);
  next.delete("focus");
  return `${pathname}?${next.toString()}${hash}`;
}

export function pushLocalView(pathname: string, params: Pick<URLSearchParams, "toString">, tab: string) {
  window.history.pushState(null, "", localViewHref(pathname, params, tab));
}
