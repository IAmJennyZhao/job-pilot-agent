import type { DashboardSankey } from "@/lib/types";

export const funnelStages = ["Saved", "Applied", "Recruiter Screen", "Tech Screen", "Final Interview", "Offer"];
export const funnelOutcomes = ["Rejected", "Withdrawn", "Ghosted"];

export function funnelHref(stage: string, since: string, from?: string, stopped = false) {
  const query = new URLSearchParams({ funnel: stage });
  if (from) query.set("from", from);
  if (stopped) query.set("stopped", "true");
  if (since) query.set("since", since);
  return `/jobs?${query.toString().replace(/\+/g, "%20")}`;
}

/** Adjacent-column Sankey. Each exit ends at its furthest stage, so terminal
 * outcomes are split by source rather than routed across unrelated stages.
 * All rectangles and ribbons share one scale; hit targets never affect it.
 */
export function layoutFunnel(sankey: DashboardSankey) {
  const total = sankey.nodes.find(node => node.id === "Saved")?.count ?? 0;
  const scale = total ? 240 / total : 0;
  const stages = funnelStages.map((id, index) => {
    const node = sankey.nodes.find(item => item.id === id);
    const outgoing = sankey.links.filter(link => link.source === id);
    const count = node?.count ?? 0;
    return { id, count, recorded: node?.recorded_count ?? 0, stopped: count - outgoing.reduce((sum, link) => sum + link.value, 0), x: 24 + index * 180, y: 65, height: count * scale };
  });
  const flows = stages.flatMap((stage, index) => {
    const outgoing = sankey.links.filter(link => link.source === stage.id && link.value > 0);
    const continuation = outgoing.find(link => link.target === funnelStages[index + 1]);
    const exits = [
      ...(stage.stopped > 0 ? [{ source: stage.id, target: "No later stage", value: stage.stopped, stopped: true }] : []),
      ...funnelOutcomes.flatMap(target => outgoing.filter(link => link.target === target).map(link => ({ ...link, stopped: false })))
    ];
    let offset = continuation?.value ?? 0;
    let exitY = 65 + offset * scale + 56;
    const destinations = [
      ...(continuation ? [{ ...continuation, stopped: false, y: 65 }] : []),
      ...exits.map(exit => { const result = { ...exit, y: exitY }; exitY += exit.value * scale + 56; return result; })
    ];
    offset = 0;
    return destinations.map(link => {
      const height = link.value * scale;
      const x1 = stage.x + 12, x2 = stage.x + 180;
      const y1 = stage.y + offset * scale, y2 = link.y;
      offset += link.value;
      const path = `M${x1},${y1} C${x1 + 70},${y1} ${x2 - 70},${y2} ${x2},${y2} L${x2},${y2 + height} C${x2 - 70},${y2 + height} ${x1 + 70},${y1 + height} ${x1},${y1 + height} Z`;
      return { ...link, height, x: x2, path, centerPath: `M${x1},${y1 + height / 2} C${x1 + 70},${y1 + height / 2} ${x2 - 70},${y2 + height / 2} ${x2},${y2 + height / 2}`, exit: link.stopped || funnelOutcomes.includes(link.target) };
    });
  });
  return { total, scale, stages, flows, width: 1280, height: Math.max(390, ...flows.map(flow => flow.y + flow.height + 48)) };
}
