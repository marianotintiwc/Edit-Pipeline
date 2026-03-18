import { expect, test } from "@playwright/test";

import { attachApiMocks } from "./fixtures/api-mocks";

test.describe("Runs usability flow", () => {
  test("renders runs list and selected run details", async ({ page }) => {
    await attachApiMocks(page);
    await page.goto("/runs");

    await expect(page.getByRole("heading", { name: "Track active work and recover failures" })).toBeVisible();
    await expect(page.getByText("Recent runs", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Open run-1" }).click();
    await expect(page.getByRole("heading", { name: "Selected run" })).toBeVisible();
    await expect(page.getByText("Rendering video")).toBeVisible();
  });

  test("shows empty-state CTA when no runs exist", async ({ page }) => {
    await attachApiMocks(page, { runsResponse: { items: [] } });
    await page.goto("/runs");

    await expect(page.getByText("No runs yet")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start in Studio" })).toBeVisible();
  });
});
