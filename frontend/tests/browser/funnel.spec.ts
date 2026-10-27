import { openAnalytics } from "./review-capture";
import { expect, test } from "@playwright/test";
import { funnelStages, layoutFunnel } from "../../src/lib/funnel-layout";
import type { DashboardSankey } from "../../src/lib/types";
import { captureWorkspaceArea } from "./review-capture";

const backend = "http://127.0.0.1:8100";

test("layout conserves flows with a common scale, including tiny and zero counts", () => {
  const graph: DashboardSankey = {
    nodes: funnelStages.map((id, index) => ({ id, label: id, kind: "stage", recorded_count: 0, count: index === 0 ? 10000 : index === 1 ? 2 : 0 })),
    links: [{ source: "Saved", target: "Applied", value: 2 }, { source: "Saved", target: "Rejected", value: 1 }]
  };
  const layout = layoutFunnel(graph);
  for (const stage of layout.stages) {
    const flows = layout.flows.filter(flow => flow.source === stage.id);
    expect(flows.reduce((sum, flow) => sum + flow.value, 0)).toBe(stage.count);
    expect(flows.reduce((sum, flow) => sum + flow.height, 0)).toBeCloseTo(stage.height);
    expect(stage.height).toBeCloseTo(stage.count * layout.scale);
  }
  const tiny = layout.flows.find(flow => flow.target === "Rejected")!;
  expect(tiny.height).toBe(0.024); // No artificial minimum / maximum for the visible ribbon.
  expect(layout.flows.find(flow => flow.target === "Applied")!.height).toBe(tiny.height * 2);
  expect(layout.flows.every(flow => flow.value > 0 && !flow.path.includes("NaN"))).toBeTruthy();
  const zero = layoutFunnel({ nodes: [], links: [] });
  expect(zero.flows).toEqual([]);
  expect(zero.stages.every(stage => stage.height === 0)).toBeTruthy();
  expect(zero.height).toBeGreaterThan(0);
  const single = layoutFunnel({ nodes: [{ id: "Saved", label: "Saved", count: 1, recorded_count: 1, kind: "stage" }], links: [] });
  expect(single.flows).toHaveLength(1);
  expect(single.flows[0]).toMatchObject({ value: 1, height: 240, stopped: true });
});

test("chart and counts retain exact cohorts, keyboard links and mobile access", async ({ page, request }, info) => {
  const since = "2000-01-01";
  const response = await request.get(`${backend}/api/dashboard/summary?saved_since=${since}`);
  const graph: DashboardSankey = (await response.json()).sankey;
  const layout = layoutFunnel(graph);
  await page.goto(`/dashboard?since=${since}`);
  const cohort = page.locator("details").filter({ has: page.locator("summary").filter({ hasText: /^Analytics cohort/ }) }).first();
  await expect(cohort).not.toHaveAttribute("open", "");
  await expect(page.getByLabel("Jobs saved on or after (UTC)", { exact: true })).toBeHidden();
  await expect(page.getByRole("heading", { name: "Application Sankey", exact: true })).toBeVisible();
  const region = page.getByRole("region", { name: "Application funnel visualization", exact: true });
  await expect(region.getByText(/^Flow thickness represents/)).toHaveClass("sr-only");
  await expect(region.getByText(`${layout.total} tracked jobs`, { exact: true })).toBeVisible();
  await expect(region.locator("[data-flow]")).toHaveCount(layout.flows.length);
  for (const flow of layout.flows) {
    const ribbon = region.locator(`[data-flow="${flow.source}:${flow.target}"]`);
    await expect(ribbon).toHaveAttribute("data-thickness", String(flow.height));
    await expect(ribbon).toHaveAttribute("data-count", String(flow.value));
  }
  const scroller = page.getByRole("region", { name: "Scrollable proportional funnel" });
  await scroller.focus();
  if (info.project.name === "mobile") {
    await page.keyboard.press("ArrowRight");
    await expect.poll(() => scroller.evaluate(element => element.scrollLeft)).toBeGreaterThan(0);
  }
  await scroller.evaluate(element => { element.scrollLeft = 0; });
  await scroller.focus();
  await page.keyboard.press("Tab");
  await expect(region.locator("svg a").first()).toBeFocused();
  await region.getByRole("button", { name: "Chart", exact: true }).focus();
  await captureWorkspaceArea(page, info, "funnel-chart.png", region);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();

  const branch = region.getByRole("link", { name: "1 jobs rejected after Tech Screen", exact: true });
  await branch.focus();
  await expect(branch).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/funnel=Rejected&from=Tech%20Screen&since=2000-01-01/);
  await expect(page.getByText("Synthetic Rejected Co", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Synthetic Applied Co", { exact: true })).toHaveCount(0);
  await page.goBack();
  await region.getByRole("button", { name: "Counts & drill-downs" }).click();
  await expect(region.getByRole("list", { name: "Stages reached" })).toBeVisible();
  // Capture the final button colors, not the middle of its CSS transition.
  await region.getByRole("button", { name: "Counts & drill-downs" }).evaluate(async element => {
    await Promise.all(element.getAnimations().map(animation => animation.finished));
  });
  await captureWorkspaceArea(page, info, "funnel-counts.png", region);
  for (const flow of layout.flows) {
    const source = flow.stopped ? flow.source : flow.target;
    const url = new URLSearchParams({ funnel_stage: source, saved_since: since });
    if (flow.stopped) url.set("funnel_stopped", "true"); else url.set("funnel_from", flow.source);
    const result = await request.get(`${backend}/api/jobs?${url}`);
    expect((await result.json()).length).toBe(flow.value);
  }
  const stop = region.getByRole("link", { name: /jobs with no later stage after Saved,/ });
  await stop.click();
  await expect(page).toHaveURL(/funnel=Saved&stopped=true&since=2000-01-01/);
  await expect(page.getByRole("heading", { name: "Jobs with no later stage after Saved" })).toBeVisible();
  await expect(page.getByText("Historical cohort · excludes closed and archived jobs", { exact: true })).toBeVisible();
  await expect(page.getByText("Synthetic Saved Co", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Synthetic Applied Co", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Jobs with no later stage after Saved" })).toBeVisible();
  await page.getByRole("button", { name: "Remove funnel filter" }).click();
  await expect(page).not.toHaveURL(/stopped=/);
});

test("empty cohorts keep zero counts accessible and synchronize with Outcomes", async ({ page }) => {
  await page.goto("/dashboard?since=2099-01-01");
  const region = page.getByRole("region", { name: "Application funnel visualization", exact: true });
  await expect(region.getByText("0 tracked jobs", { exact: true })).toBeVisible();
  await expect(region.locator("[data-flow]")).toHaveCount(0);
  await region.getByRole("button", { name: "Counts & drill-downs" }).click();
  await expect(region.getByRole("link", { name: "Saved: 0", exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Dashboard views" }).getByRole("button", { name: "Outcomes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "0 saved jobs in this cohort", exact: true })).toBeVisible();
  await openAnalytics(page);
  await expect(page.getByLabel("Jobs saved on or after (UTC)", { exact: true })).toHaveValue("2099-01-01");
  await page.goBack();
  await expect(region).toBeVisible();
  await openAnalytics(page);
  await page.getByRole("button", { name: "All time", exact: true }).click();
  await expect(region.getByText("0 tracked jobs", { exact: true })).toHaveCount(0);
});
