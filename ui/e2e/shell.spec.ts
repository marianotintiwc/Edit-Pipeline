import { expect, test } from "@playwright/test";

import { attachApiMocks } from "./fixtures/api-mocks";

test.describe("Shell navigation usability", () => {
  test.beforeEach(async ({ page }) => {
    await attachApiMocks(page);
  });

  test("exposes all primary navigation entries", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByRole("navigation", { name: "Primary" });

    await expect(page.getByRole("heading", { name: "UGC Video Editor" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Studio" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Batch" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Runs" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Library" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Admin" })).toBeVisible();
  });

  test("navigates to all top-level screens", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Studio" }).click();
    await expect(page.getByRole("heading", { name: "Choose a starting point" })).toBeVisible();

    await page.getByRole("link", { name: "Batch" }).click();
    await expect(page.getByRole("heading", { name: "Batch assistant" })).toBeVisible();

    await page.getByRole("link", { name: "Runs" }).click();
    await expect(page.getByRole("heading", { name: "Track active work and recover failures" })).toBeVisible();

    await page.getByRole("link", { name: "Library" }).click();
    await expect(page.getByRole("heading", { name: "Shared recipes, assets, and brand kits" })).toBeVisible();

    await page.getByRole("link", { name: "Admin" }).click();
    await expect(page.getByRole("heading", { name: "Provider defaults and guardrails" })).toBeVisible();
  });
});
