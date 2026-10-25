import { expect, test } from "@playwright/test";
import { addEmployee, api, enterClaim, signedInAdmin } from "./helpers";
import { EDGE_HEADERS } from "./env";

test("an admin of another organisation cannot reach this organisation's data", async ({ page, browser }) => {
  // Organisation A: an employee and a claim with its receipt.
  await signedInAdmin(page, "org-a");
  const employee = await addEmployee(page, { name: "Secret Bekele", department: "A-Only Department" });
  await enterClaim(page, "Secret Bekele", { receipt: "A-1" });
  const claimId = page.url().split("/").pop()!;
  const claim = await (await api(page, "GET", `claims/${claimId}`)).json();

  // Organisation B's admin, in another browser.
  const other = await browser.newContext({ extraHTTPHeaders: EDGE_HEADERS });
  const b = await other.newPage();
  await signedInAdmin(b, "org-b");

  await b.goto(`/claims/${claimId}`);
  await expect(b.getByRole("heading", { name: "Claim not found" })).toBeVisible();
  await expect(b.getByTestId("not-found").filter({ visible: true })).toHaveText("Not found.");
  for (const path of [`claims/${claimId}`, `employees/${employee.id}`]) {
    const resp = await api(b, "GET", path);
    expect(resp.status()).toBe(404);
    expect(await resp.json()).toEqual({ error: "Not found.", error_code: "NOT_FOUND" });
  }
  expect((await api(b, "POST", `employees/${employee.id}/deactivate`)).status()).toBe(404);
  // Approving needs a fresh code first, whoever asks; with one, it is 404 too (tested in pytest).
  expect((await api(b, "POST", `claims/${claimId}/approve`)).status()).toBe(403);
  expect((await api(b, "PATCH", `employees/${employee.id}`, { name: "Hijacked" })).status()).toBe(404);
  expect((await b.request.get(`/api/receipts/${claim.receipt_file_id}`)).status()).toBe(404);

  // Lists, reports and exports show B only its own (empty) data.
  await b.goto("/employees");
  await expect(b.getByTestId("kpi-active").filter({ visible: true })).toHaveText("0");
  await expect(b.getByText("Secret Bekele")).toHaveCount(0);
  await b.goto("/claims");
  await expect(b.getByTestId("tab-count-all").filter({ visible: true })).toHaveText("0");
  const exported = await (await b.request.get("/api/export/employees/export")).text();
  expect(exported).not.toContain("Secret");
  const report = await (await api(b, "GET", "reports")).json();
  expect(report.totals.claims).toBe(0);
  await other.close();

  // A still sees its own.
  await page.goto(`/claims/${claimId}`);
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Pending");
});
