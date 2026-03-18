import { expect, test } from "@playwright/test";

import { attachApiMocks } from "./fixtures/api-mocks";

test.describe("Studio usability flow", () => {
  test.beforeEach(async ({ page }) => {
    await attachApiMocks(page);
  });

  test("lets users select preset, preview, and launch", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("link", { name: "Studio" }).click();
    await expect(page.getByRole("heading", { name: "Choose a starting point" })).toBeVisible();

    await page.getByRole("button", { name: "Use MELI Edit Classic", exact: true }).click();
    await expect(page.getByLabel("Market / country configuration")).toHaveValue("MLB");

    const clipInputs = page.getByLabel(/Clip URL/i);
    await clipInputs.nth(1).fill("https://example.com/scene2.mp4");

    await page.getByRole("button", { name: "Preview render plan" }).click();
    await expect(page).toHaveURL(/\/studio\/review$/);
    await expect(page.getByText("Preview warning")).toBeVisible({ timeout: 15000 });
    const reviewSection = page.getByRole("region", { name: "Review & submit" });
    await expect(reviewSection.getByText("2 resolved clips")).toBeVisible();

    await page.getByRole("button", { name: "Launch run" }).click();
    await expect(page.getByText("Run launched")).toBeVisible();
    await expect(page.getByText("Run ID: run-1")).toBeVisible();
    await expect(page).toHaveURL(/\/runs$/);
  });

  test("blocks preview when clips are removed", async ({ page }) => {
    await page.goto("/studio/brief");
    await page.getByRole("button", { name: "Use MELI Edit Classic", exact: true }).click();

    await page.getByRole("button", { name: "Remove clip" }).nth(1).click();
    await page.getByRole("button", { name: "Remove clip" }).click();

    await expect(page.getByRole("button", { name: "Preview render plan" })).toBeDisabled();
    await expect(page.getByText(/No clips added yet/)).toBeVisible();
  });
});
