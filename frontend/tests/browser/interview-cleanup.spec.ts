import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { captureWorkspace, captureWorkspaceArea } from "./review-capture";

const backend = "http://127.0.0.1:8100";
async function practice(request: APIRequestContext, count = 3) {
  const response = await request.post(`${backend}/api/interview/practice-sets`, { data: { target_category: "Backend Engineer", target_role: `Interview review ${Date.now()}`, count } });
  expect(response.ok()).toBeTruthy();
  return response.json();
}
async function evaluate(request: APIRequestContext, set: { session_id: string; questions: { id: string }[] }, index = 0, answer = "A saved API answer") {
  const response = await request.post(`${backend}/api/interview/answers/evaluate`, { data: { session_id: set.session_id, question_id: set.questions[index].id, answer, elapsed_seconds: 45, time_limit_seconds: 120 } });
  expect(response.ok()).toBeTruthy();
}
const tabs = (page: Page) => page.getByRole("navigation", { name: "Interview views", exact: true });
const elapsed = async (page: Page) => {
  const text = await page.getByRole("timer", { name: "Answer elapsed time" }).innerText();
  const [minutes, seconds] = text.split(":").map(Number);
  return minutes * 60 + seconds;
};

test("Practice keeps drafts and a running timer through History, session detail and refresh", async ({ page, request }, info) => {
  const set = await practice(request);
  await page.clock.install();
  await page.goto(`/interview?resumeSessionId=${set.session_id}`);
  const answer = `Unsaved answer ${set.session_id}`;
  await page.getByLabel("Your answer", { exact: true }).fill(answer);
  await expect(page.getByRole("heading", { name: "Session History", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /^Answer attempts/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Interview Insights", exact: true })).toHaveCount(0);
  await expect(page.locator("summary", { hasText: "Questions: 1 of" })).toBeVisible();
  await page.getByLabel("Answer time target", { exact: true }).selectOption("60");
  await page.getByRole("button", { name: "Start timer", exact: true }).click();
  await page.clock.fastForward(6500);
  await expect.poll(() => elapsed(page)).toBeGreaterThanOrEqual(6);
  await tabs(page).getByRole("button", { name: "History", exact: true }).click();
  await expect(page).toHaveURL(/tab=history/);
  await expect(page.getByRole("heading", { name: "Session History", exact: true })).toBeVisible();
  await page.clock.fastForward(4000);
  await tabs(page).getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(answer);
  await expect.poll(() => elapsed(page)).toBeGreaterThanOrEqual(10);
  await page.reload();
  await expect(page.getByRole("button", { name: "Pause timer", exact: true })).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(answer);
  await expect(page.getByLabel("Answer time target", { exact: true })).toHaveValue("60");
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  await expect(page.locator("#current-attempts")).toBeVisible();
  await page.locator(`a[href="/interview/sessions/${set.session_id}"]`).click();
  await expect(page.getByRole("button", { name: "Continue unanswered questions", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Back to Interview History", exact: true }).click();
  await tabs(page).getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(answer);
  await expect(page.getByRole("button", { name: "Pause timer", exact: true })).toBeVisible();
  await page.clock.fastForward(65000);
  await expect(page.getByText("Time target reached. Finish your thought, then evaluate when ready.", { exact: true })).toBeVisible();
  expect((await (await request.get(`${backend}/api/interview/sessions/${set.session_id}`)).json()).messages.filter((message: { role: string }) => message.role === "user")).toHaveLength(0);
  await captureWorkspace(page, info, "focused-practice.png");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
});

test("History owns comparisons while current-question revision preserves the replacement decision", async ({ page, request }, info) => {
  const set = await practice(request, 1);
  await evaluate(request, set, 0, `Earlier answer ${set.session_id}`);
  await evaluate(request, set, 0, `Latest answer ${set.session_id}`);
  // Keep this exact question active using the same durable draft format the app writes.
  await page.goto("/interview");
  await page.evaluate(set => {
    const state = { practiceSet: set, queue: set.questions, activeQuestionId: set.questions[0].id, answers: { [`${set.session_id}:${set.questions[0].id}`]: "Local editing draft to preserve" } };
    sessionStorage.setItem("job-pilot:draft:interview-practice", JSON.stringify(state));
  }, set);
  await page.reload();
  await page.getByRole("button", { name: "Start timer", exact: true }).click();
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  const comparisons = page.locator("#current-attempts").locator("..");
  await expect(comparisons.getByRole("heading", { name: /^Answer attempts/ })).toBeVisible();
  await expect(comparisons.getByText(`Latest answer ${set.session_id}`, { exact: true })).toBeVisible();
  await comparisons.getByRole("button", { name: "Revise this answer", exact: true }).last().click();
  const dialog = page.getByRole("dialog", { name: "Confirm change", exact: true });
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await tabs(page).getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("Local editing draft to preserve");
  await expect(page.getByRole("button", { name: "Pause timer", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  await comparisons.getByRole("button", { name: "Revise this answer", exact: true }).last().click();
  await dialog.getByRole("button", { name: "Replace draft", exact: true }).click();
  await expect(tabs(page).getByRole("button", { name: "Practice", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue(`Latest answer ${set.session_id}`);
  await expect(page.getByRole("timer")).toHaveText("0:00");
  await page.getByRole("button", { name: "Review attempts in History", exact: true }).click();
  await captureWorkspaceArea(page, info, "history-comparisons.png", comparisons);
  const attempts = await (await request.get(`${backend}/api/interview/questions/${set.questions[0].id}/attempts`)).json();
  expect(attempts.filter((entry: { session_id: string }) => entry.session_id === set.session_id).map((entry: { answer: string }) => entry.answer)).toEqual([`Earlier answer ${set.session_id}`, `Latest answer ${set.session_id}`]);
});

test("History prioritizes recent feedback and accurately labels overall score subsets and old shortcuts", async ({ page, request }, info) => {
  const set = await practice(request, 1);
  await evaluate(request, set);
  await page.goto("/interview?tab=practice#interview-insights");
  await expect(page).toHaveURL(/tab=history#interview-insights/);
  await expect(page.getByRole("heading", { name: "Weaknesses to revisit", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent attempts", exact: true })).toBeVisible();
  const scoreList = page.getByRole("heading", { name: "Recent attempts", exact: true }).locator("..");
  await scoreList.getByRole("button").first().click();
  await expect(page.getByRole("button", { name: "Close insight details", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open session", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close insight details", exact: true }).click();
  const sessions = page.getByRole("heading", { name: "Session History", exact: true }).locator("../..");
  const records = await (await request.get(`${backend}/api/interview/sessions`)).json();
  if (records.length > 5) {
    await expect(sessions.getByRole("link")).toHaveCount(5);
    await sessions.getByRole("button", { name: `Show all ${records.length} sessions`, exact: true }).click();
    await expect(sessions.getByRole("link")).toHaveCount(records.length);
    await sessions.getByRole("button", { name: "Show recent five sessions", exact: true }).click();
  }
  await tabs(page).locator("summary").click();
  await tabs(page).getByRole("link", { name: "Command Center", exact: true }).click();
  await expect(page.locator("#command-center")).toBeVisible();
  const insights = await (await request.get(`${backend}/api/interview/insights`)).json();
  for (const [name, key] of [["Overall score", "overall"], ["Overall score: Knowledge tags", "knowledge"], ["Overall score: Interview skills tags", "interview_skills"]]) {
    const expected = insights.trends[key].at(-1)?.score;
    const region = page.getByRole("region", { name, exact: true });
    await expect(region.getByText(expected == null ? "--" : `${expected}/100`, { exact: true })).toBeVisible();
    await expect(region.getByText(new RegExp(`^${insights.trends[key].length} scored answers`))).toBeVisible();
  }
  await expect(page.getByText(/They are not independent subscores/)).toBeVisible();
  await captureWorkspace(page, info, "history-insights.png");
  await page.reload();
  await expect(page.locator("#command-center")).toBeVisible();
  await tabs(page).getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Session History", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
});

test("completed-session links cannot replace an active draft and continuation loads only unanswered questions", async ({ page, request }, info) => {
  const completed = await practice(request, 1);
  await evaluate(request, completed);
  const active = await practice(request, 3);
  await page.goto(`/interview?resumeSessionId=${active.session_id}`);
  await page.getByLabel("Your answer", { exact: true }).fill("Keep this active answer");
  await page.getByRole("button", { name: "Start timer", exact: true }).click();
  await page.goto(`/interview/sessions/${completed.session_id}`);
  await expect(page.getByRole("button", { name: "Resume / revise answers", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Continue unanswered questions", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Start another session", exact: true })).toBeVisible();
  await page.locator("summary", { hasText: "Saved attempts & comparisons" }).first().click();
  await expect(page.getByRole("heading", { name: /^Answer attempts/ }).first()).toBeVisible();
  await captureWorkspace(page, info, "completed-session.png");
  await page.goto(`/interview?resumeSessionId=${completed.session_id}`);
  await expect(page.getByText("No unanswered questions remain in this session. Your saved practice draft is still available.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Return to saved practice draft", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("Keep this active answer");
  await expect(page.getByRole("button", { name: "Pause timer", exact: true })).toBeVisible();
  await evaluate(request, active, 0);
  await page.goto(`/interview/sessions/${active.session_id}`);
  await page.getByRole("button", { name: "Continue unanswered questions", exact: true }).click();
  await expect(page.locator("p").filter({ hasText: active.questions[1].content })).toBeVisible();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("");
  await page.locator("summary", { hasText: "Questions:" }).click();
  await expect(page.getByRole("button").filter({ hasText: active.questions[0].content })).toHaveCount(0);
  // Imported/older feedback may have an answer snapshot without a user message.
  // The existing resume API still considers its asked question unanswered.
  const legacy = await practice(request, 1);
  expect((await request.post(`${backend}/api/interview/sessions/${legacy.session_id}/messages`, { data: {
    role: "ai", question_id: legacy.questions[0].id, content: "Older feedback", score: 70,
    feedback: { submitted_answer: "Older answer snapshot", weak_point_tags: [] }
  } })).ok()).toBeTruthy();
  await page.goto(`/interview/sessions/${legacy.session_id}`);
  await expect(page.getByRole("button", { name: "Continue unanswered questions", exact: true })).toBeVisible();
  const legacyResume = await (await request.get(`${backend}/api/interview/sessions/${legacy.session_id}/resume`)).json();
  expect(legacyResume.questions.map((question: { id: string }) => question.id)).toContain(legacy.questions[0].id);
});

test("history read failures leave active practice usable and recover independently", async ({ page, request }) => {
  const set = await practice(request);
  await page.route(`${backend}/api/interview/insights`, route => route.fulfill({ status: 503, json: { detail: "Synthetic insights unavailable" } }));
  await page.goto(`/interview?resumeSessionId=${set.session_id}`);
  await page.getByLabel("Your answer", { exact: true }).fill("Answer survives failed insights");
  await tabs(page).getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry insights", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Session History", exact: true })).toBeVisible();
  await tabs(page).getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByLabel("Your answer", { exact: true })).toHaveValue("Answer survives failed insights");
  await tabs(page).getByRole("button", { name: "History", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry insights", exact: true })).toBeVisible();
  await page.unroute(`${backend}/api/interview/insights`);
  await page.getByRole("button", { name: "Retry insights", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Interview Insights", exact: true })).toBeVisible();
  await page.route(`${backend}/api/interview/sessions`, route => route.fulfill({ status: 503, json: { detail: "Synthetic sessions unavailable" } }));
  await page.reload();
  await expect(page.getByRole("button", { name: "Retry sessions", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Interview Insights", exact: true })).toBeVisible();
  await page.unroute(`${backend}/api/interview/sessions`);
  await page.getByRole("button", { name: "Retry sessions", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Session History", exact: true })).toBeVisible();
});
