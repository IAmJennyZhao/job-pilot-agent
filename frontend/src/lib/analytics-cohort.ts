/** One first-saved-date cohort for both Dashboard analytics views.
 * Legacy aliases remain readable; an explicit `since` (even empty) wins.
 */
export function analyticsSince(params: Pick<URLSearchParams, "get">): string {
  return params.get("since") ?? params.get("saved_since") ?? params.get("outcomesSince") ?? "";
}
