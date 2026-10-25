import { expect, test } from "@playwright/test";
import { signedInAdmin } from "./helpers";

test("import employees from CSV: preview with per-row errors, then import", async ({ page }) => {
  await signedInAdmin(page, "import");
  await page.getByRole("link", { name: "Employees" }).click();
  await page.getByRole("button", { name: "Import Employees (CSV)" }).click();
  const dialog = page.getByTestId("import-dialog").filter({ visible: true });
  const bad = [
    "employee_number,name,phone,department,endod_id",
    "ET-1,Abebe Kebede,0911000001,Operations,DE100001",
    "ET-2,Bad Phone,12345,Operations,",
  ].join("\n");
  await dialog.getByLabel("Or paste the CSV").fill(bad);
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.getByTestId("import-summary")).toContainText("1 to add");
  await expect(dialog.getByTestId("import-row").nth(1)).toContainText("Phone must be an Ethiopian mobile number");
  await expect(dialog.getByRole("button", { name: /^Import/ })).toBeDisabled();

  await dialog.getByLabel("Or paste the CSV").fill(bad.replace("12345", "0911000002"));
  await dialog.getByRole("button", { name: "Preview" }).click();
  await expect(dialog.getByTestId("import-summary")).toContainText("2 to add");
  await dialog.getByRole("button", { name: "Import 2 employees" }).click();
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toHaveText(
    "Imported: 2 added, 0 updated, 0 unchanged."
  );
  await expect(page.getByTestId("employee-row").filter({ visible: true })).toHaveCount(2);

  // The export is a CSV attachment with every cell safe for a spreadsheet.
  const exported = await page.request.get("/api/export/employees/export");
  expect(exported.headers()["content-disposition"]).toMatch(/^attachment; filename="employees-\d{4}-\d{2}-\d{2}\.csv"$/);
  const text = await exported.text();
  expect(text).toContain("ET-1,Abebe Kebede,'+251911000001,Operations,DE100001");
});
