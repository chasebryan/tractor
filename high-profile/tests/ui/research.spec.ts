import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("search → inspect → source, confidence and version history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Start with the evidence." }),
  ).toBeVisible();
  await page.getByRole("searchbox").count();
  await page.getByLabel("Search public evidence").fill("China");
  await page.getByRole("button", { name: "Run search" }).click();
  await expect(page.locator(".claim-row")).toHaveCount(3);
  await page
    .getByRole("button", {
      name: "SIPRI assessed that China’s nuclear arsenal expanded and modernized during 2024.",
    })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByText("SUPPORTING EVIDENCE", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Confidence", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Why high confidence?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "History", exact: true }).click();
  await page.locator(".version-card").filter({ hasText: "Version 1" }).click();
  await expect(page.locator(".claim-reference")).toContainText("VERSION 1");
  await page
    .getByRole("button", { name: "Evidence", exact: false })
    .filter({ hasText: "Evidence" })
    .first()
    .count();
  await page
    .locator(".inspector-tabs")
    .getByRole("button", { name: /Evidence/ })
    .click();
  await expect(
    page.getByRole("link", { name: "Open original source" }),
  ).toHaveAttribute("href", "https://www.sipri.org/yearbook/2024/07");
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  expect(errors).toEqual([]);
});
test("temporal reconstruction, contradictory and multilingual evidence", async ({
  page,
}) => {
  await page.goto("/profiles/china-program");
  await page
    .getByLabel("Public evidence as of", { exact: true })
    .fill("2024-12-31");
  await expect(page.locator(".claim-row")).toContainText("2024 assessment");
  await page.reload();
  await expect(page.locator(".claim-row")).toContainText("2024 assessment");
  await page.goto("/profiles/review-scenario");
  await page
    .getByRole("button", {
      name: "SYNTHETIC: Memo A describes the illustrative programme as operating.",
    })
    .click();
  await expect(
    page.getByText("CONTRADICTORY EVIDENCE", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".contradiction-note")).toContainText("suspended");
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await page.goto("/profiles/france");
  await page
    .getByRole("button", {
      name: "In February 2020, France’s president stated that the French arsenal contained fewer than 300 nuclear weapons.",
    })
    .click();
  await expect(page.locator('blockquote[lang="fr"]')).toContainText(
    "inférieure",
  );
  await expect(page.locator(".translation")).toContainText("fewer than 300");
});
test("source ledger, empty states and responsive navigation", async ({
  page,
  isMobile,
}) => {
  await page.goto("/sources");
  await page.getByLabel("Search source ledger").fill("SIPRI");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".ledger-row")).toHaveCount(2);
  await page.getByLabel("Source health").selectOption("SUPERSEDED");
  await expect(page.locator(".ledger-row")).toHaveCount(1);
  await page.locator(".ledger-row").click();
  await expect(
    page.getByRole("heading", { name: "Retrieval records" }),
  ).toBeVisible();
  await page.goto("/search?q=nonexistent-evidence");
  await expect(
    page.getByRole("heading", { name: "No matching evidence" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("link", { name: "Entities", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Entity directory" }),
    ).toBeVisible();
  }
});
test("investigation saves exact versions and survives reload", async ({
  page,
}) => {
  await page.goto("/profiles/china-program");
  await page.locator(".claim-statement").click();
  await page.getByRole("button", { name: "History", exact: true }).click();
  await page.locator(".version-card").filter({ hasText: "Version 1" }).click();
  await expect(page.locator(".claim-reference")).toContainText("VERSION 1");
  await page.getByText("Save to investigation", { exact: true }).click();
  const title = `UI verification ${test.info().project.name} ${Date.now()}`;
  await page.getByLabel("New investigation title").fill(title);
  await page
    .getByLabel("Analyst note")
    .fill("Retain the superseded 2024 assessment.");
  await page.getByRole("button", { name: "Save this version" }).click();
  await expect(page.getByRole("status")).toContainText("Claim version saved");
  await page.getByRole("button", { name: "Close evidence inspector" }).click();
  await page.goto("/investigations");
  await page.getByRole("link").filter({ hasText: title }).click();
  await page.reload();
  await expect(page.locator(".saved-items")).toContainText(
    "Retain the superseded 2024 assessment.",
  );
  await expect(
    page.getByRole("link", { name: "Export cited report" }),
  ).toBeVisible();
  await page.locator(".saved-items .claim-statement").click();
  await expect(page.locator(".claim-reference")).toContainText("VERSION 1");
  await expect(page.locator(".inspector")).toContainText("2024 assessment");
});
test("keyboard, accessibility and layout audit", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".claim-row").first()).toBeVisible();
  await page.keyboard.press("/");
  await expect(page.getByLabel("Search public evidence")).toBeFocused();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `../../work/high-profile-${test.info().project.name}.png`,
    fullPage: true,
  });
});

test("research pages and evidence inspector meet automated accessibility checks", async ({
  page,
}) => {
  test.setTimeout(90000);
  for (const route of [
    "/directory",
    "/profiles/barakah",
    "/sources",
    "/methodology",
    "/investigations",
  ]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      results.violations.map((v) => ({
        id: v.id,
        nodes: v.nodes.map((n) => ({
          target: n.target,
          summary: n.failureSummary,
        })),
      })),
      route,
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      route,
    ).toBe(true);
  }
  await page.goto("/profiles/review-scenario");
  await page
    .getByRole("button", {
      name: "SYNTHETIC: Memo A describes the illustrative programme as operating.",
    })
    .click();
  await expect(
    page.getByText("CONTRADICTORY EVIDENCE", { exact: true }),
  ).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
