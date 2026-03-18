import { expect, test } from "@playwright/test";

import { attachApiMocks } from "./fixtures/api-mocks";

test("cross-flow journey: Home -> Studio -> Runs -> Batch", async ({ page }) => {
  await attachApiMocks(page);
  await page.goto("/");

  await page.getByRole("link", { name: "Studio" }).click();
  await page.getByRole("button", { name: "Use MELI Edit Classic", exact: true }).click();
  await expect(page).toHaveURL(/\/studio\/brief$/);

  const clipInputs = page.getByLabel(/Clip URL/i);
  await clipInputs.nth(1).fill("https://example.com/scene2.mp4");
  await page.getByRole("button", { name: "Preview render plan" }).click();
  await expect(page).toHaveURL(/\/studio\/review$/);
  await expect(page.getByText("Preview warning")).toBeVisible({ timeout: 15000 });

  await page.getByRole("button", { name: "Launch run" }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByText("Recent runs", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Batch" }).click();
  await expect(page).toHaveURL(/\/batch\/import$/);
  await expect(page.getByText("Load existing batch")).toBeVisible();
});
