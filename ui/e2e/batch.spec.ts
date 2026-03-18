import { expect, test } from "@playwright/test";

import { attachApiMocks } from "./fixtures/api-mocks";

const CSV_CONTENT = `geo,subtitle_mode,clips[0].type,clips[0].url
MLA,auto,scene,https://example.com/scene1.mp4
`;

test.describe("Batch usability flow", () => {
  test.beforeEach(async ({ page }) => {
    await attachApiMocks(page);
  });

  test("supports step navigation and upload preview flow", async ({ page }) => {
    await page.goto("/batch/import");
    await expect(page.getByRole("heading", { name: "Batch assistant" })).toBeVisible();

    await page.getByRole("link", { name: "Schema mapping" }).click();
    await expect(page.getByText("No CSV loaded yet")).toBeVisible();

    await page.getByRole("link", { name: "Batch preview" }).click();
    await expect(page.getByText("No batch loaded")).toBeVisible();

    await page.goto("/batch/import");
    await page.getByLabel("CSV batch file").setInputFiles({
      name: "jobs.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(CSV_CONTENT, "utf-8"),
    });

    await expect(page.getByText("batch-1")).toBeVisible();
    await expect(page.getByText("1 valid row")).toBeVisible();
    await expect(page.getByRole("button", { name: "Submit pending rows" })).toBeVisible();

    await page.getByRole("button", { name: "Submit pending rows" }).click();
    await expect(page.getByRole("heading", { name: "Submission progress" })).toBeVisible();
  });

  test("shows clear upload error guidance", async ({ page }) => {
    await page.route("**/api/batches", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({
            errors: ["Batch upload must be a UTF-8 encoded CSV file"],
          }),
        });
        return;
      }
      await route.fallback();
    });

    await page.goto("/batch/import");
    await page.getByLabel("CSV batch file").setInputFiles({
      name: "jobs.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("x", "utf-8"),
    });

    await expect(page.getByRole("alert")).toContainText("Upload failed");
    await expect(page.getByRole("alert")).toContainText("Check CSV format and size, then try again.");
  });
});
