import fs from "node:fs";
import { expect, test } from "@playwright/test";
import { addEmployee, api, enterClaim, reauthenticate, signedInAdmin } from "./helpers";

test("add an employee, enter a claim with its receipt, approve, batch, export and mark paid", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "flow");

  // Add an employee on the Employees page.
  await page.getByRole("link", { name: "Employees" }).click();
  await page.getByRole("button", { name: "Add Single Employee" }).click();
  const dialog = page.getByTestId("employee-dialog").filter({ visible: true });
  await dialog.getByLabel("Full Name").fill("Dawit Bekele");
  await dialog.getByLabel("Employee Number").fill("ET-0492");
  await dialog.getByLabel("Department").fill("Engineering");
  await dialog.getByLabel("Mobile Phone").fill("0911223344");
  await dialog.getByLabel("ENDOD ID (optional)").fill("de-000492");
  await dialog.getByLabel("Payout Method").selectOption("cbe");
  await dialog.getByLabel(/Payout Account/).fill("1000123456789");
  await dialog.getByRole("button", { name: "Add Employee" }).click();
  // A payout account is where reimbursements go: a fresh code is asked for.
  await reauthenticate(page, auth);
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toHaveText("Dawit Bekele is added.");
  const row = page.getByTestId("employee-row").filter({ hasText: "Dawit Bekele" });
  await expect(row).toContainText("+251911223344");
  await expect(row).toContainText("DE000492");
  await row.getByRole("button", { name: "View Profile" }).click();
  await expect(page.getByTestId("drawer-name").filter({ visible: true })).toHaveText("Dawit Bekele");
  await page.getByRole("button", { name: "Close detail pane" }).click();

  // Enter the claim with a receipt photo.
  await enterClaim(page, "Dawit Bekele", { receipt: "FS-1001", quantity: "2", price: "250.50" });
  await expect(page.getByTestId("payable").filter({ visible: true })).toHaveText("ETB 501.00");
  const receiptHref = await page.getByRole("link", { name: "View", exact: true }).getAttribute("href");
  const receipt = await page.request.get(receiptHref!);
  expect(receipt.status()).toBe(200);
  expect(receipt.headers()["content-type"]).toBe("image/png");
  expect(receipt.headers()["x-content-type-options"]).toBe("nosniff");
  expect(receipt.headers()["content-disposition"]).toMatch(/^inline; filename="receipt.png"/);
  await expect(page.getByTestId("pending-badge").filter({ visible: true })).toHaveText("1");

  // Approve (the code given for the payout account a moment ago still counts: 10 minutes).
  await page.getByRole("button", { name: /^Approve/ }).click();
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toContainText("is approved: ETB 501.00 will be paid back to Dawit Bekele");
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Approved");

  // Batch it for CBE, download the bank file.
  await page.getByRole("link", { name: "Payments" }).click();
  await expect(page.getByTestId("kpi-ready").filter({ visible: true })).toHaveText("ETB 501.00");
  await page.getByTestId("method-cbe").filter({ visible: true }).getByRole("button", { name: "Create batch" }).click();
  await page.getByTestId("batch-dialog").filter({ visible: true }).getByRole("button", { name: "Create batch" }).click();
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toContainText("BATCH-0001 is ready: 1 claims, ETB 501.00");
  const batchRow = page.getByTestId("batch-row").filter({ hasText: "BATCH-0001" });
  const downloading = page.waitForEvent("download");
  await batchRow.getByRole("link", { name: "Download file" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe("BATCH-0001-cbe.csv");
  const csv = fs.readFileSync((await download.path())!, "utf-8");
  expect(csv).toContain("1000123456789,Dawit Bekele,501.00,BATCH-0001/CLM-000001");
  // Downloaded, the batch may have been paid at the bank: it can no longer be cancelled.
  await expect(batchRow.getByRole("button", { name: "Cancel" })).toHaveCount(0);

  // Mark it paid with the bank's reference (the code given for the approval still counts).
  await batchRow.getByRole("button", { name: "Mark paid" }).click();
  const paid = page.getByTestId("paid-dialog").filter({ visible: true });
  await paid.getByLabel("Bank or Telebirr reference").fill("FT26298ABCD");
  await paid.getByRole("button", { name: "Mark paid" }).click();
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toContainText("BATCH-0001 is marked paid (reference FT26298ABCD)");
  await expect(page.getByTestId("batch-reference").filter({ visible: true })).toContainText("Ref: FT26298ABCD");
  await expect(page.getByTestId("batch-row").filter({ visible: true }).getByRole("button", { name: "Mark paid" })).toHaveCount(0);

  // The claim and the overview follow.
  await page.getByRole("link", { name: /^Claims( [0-9]+)?$/ }).click();
  await page.getByRole("tab", { name: /^Paid/ }).click();
  await expect(page.getByTestId("claim-row").filter({ visible: true })).toHaveCount(1);
  await page.getByRole("link", { name: "Overview" }).click();
  await expect(page.getByTestId("kpi-reimbursed").filter({ visible: true })).toHaveText("ETB 501.00");

  // Reports and their CSV.
  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.getByTestId("report-spend").filter({ visible: true })).toHaveText("ETB 501.00");
  await expect(page.getByTestId("by-medicine").filter({ visible: true })).toContainText("Metformin 500mg");
  const report = await page.request.get("/api/export/reports/export?kind=department");
  expect(report.headers()["content-type"]).toContain("text/csv");
  expect(await report.text()).toContain("Engineering,1,1,501.00,501.00");
});

test("reject a claim with a reason", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "reject");
  await addEmployee(page, { name: "Meron Assefa" });
  await enterClaim(page, "Meron Assefa", { receipt: "LP-77" });
  await page.getByRole("button", { name: "Reject Claim" }).click();
  const dialog = page.getByTestId("reject-dialog").filter({ visible: true });
  await expect(dialog.getByRole("button", { name: "Reject" })).toBeDisabled();
  await dialog.getByLabel("Reason (required)").fill("The receipt has no pharmacy stamp.");
  await dialog.getByRole("button", { name: "Reject" }).click();
  await reauthenticate(page, auth);
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Rejected");
  await expect(page.getByTestId("rejection-reason").filter({ visible: true })).toHaveText("The receipt has no pharmacy stamp.");
  await expect(page.getByRole("button", { name: /^Approve/ })).toHaveCount(0);

  // The same receipt may be entered again after a rejection; a second copy is refused.
  await enterClaim(page, "Meron Assefa", { receipt: "LP-77" });
  await page.goto("/claims/new");
  await page.getByLabel("Find employee").fill("Meron Assefa");
  await page.getByTestId("employee-option").filter({ visible: true }).first().click();
  await page.getByLabel("Pharmacy name").fill("Kenema Pharmacy Bole");
  await page.getByLabel("Pharmacy TIN").fill("0012345678");
  await page.getByLabel("Receipt number").fill("lp-77");
  await page.getByLabel("Medicine 1").fill("Amoxicillin");
  await page.getByLabel("Unit price (ETB) 1").fill("80");
  await page.getByLabel(/Receipt file/).setInputFiles({ name: "again.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n%%EOF\n") });
  await expect(page.getByTestId("receipt-uploaded").filter({ visible: true })).toBeVisible();
  await page.getByRole("button", { name: "Save claim" }).click();
  await expect(page.getByTestId("form-error").filter({ visible: true })).toContainText("is already claimed on CLM-000002");
});

test("a fake image is refused", async ({ page }) => {
  await signedInAdmin(page, "fake");
  await addEmployee(page, { name: "Yonas Girma" });
  await page.goto("/claims/new");
  await page.getByLabel(/Receipt file/).setInputFiles({ name: "receipt.png", mimeType: "image/png", buffer: Buffer.from("<html><script>alert(1)</script>") });
  await expect(page.getByTestId("form-error").filter({ visible: true })).toHaveText("Only PDF, JPEG, PNG or WebP files can be attached.");
});

test("the annual limit caps the reimbursement, then refuses", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "limit");
  // Lower the limit on the Settings page (a fresh code is asked for).
  await page.getByRole("link", { name: "Policy & Settings" }).click();
  await page.getByLabel("Annual limit per employee (ETB)").fill("1,000");
  await page.getByLabel("Employee co-pay (%)").fill("10");
  await page.getByRole("button", { name: "Save policy" }).click();
  await reauthenticate(page, auth);
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toHaveText("The benefit policy is saved.");

  await addEmployee(page, { name: "Rahel Mengistu" });
  // ETB 1,500.00, 10% co-pay: the share is ETB 1,350.00, more than the ETB 1,000.00 limit.
  await enterClaim(page, "Rahel Mengistu", { receipt: "KD-1", quantity: "1", price: "1500" });
  await expect(page.getByTestId("cap-warning").filter({ visible: true })).toContainText("only ETB 1,000.00 will be reimbursed");
  await expect(page.getByTestId("payable").filter({ visible: true })).toHaveText("ETB 1,000.00");
  await page.getByRole("button", { name: /^Approve/ }).click();
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Approved");
  await expect(page.getByTestId("approval-note").filter({ visible: true })).toContainText("capped at the remaining annual limit: ETB 1,000.00 is paid back");

  // Nothing is left: the next claim cannot be approved.
  await enterClaim(page, "Rahel Mengistu", { receipt: "KD-2", quantity: "1", price: "40" });
  await expect(page.getByTestId("problems").filter({ visible: true })).toContainText("annual limit of ETB 1,000.00 is used up");
  await page.getByRole("button", { name: /^Approve/ }).click();
  await expect(page.getByTestId("action-error").filter({ visible: true })).toContainText("is used up");
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Pending");
  expect((await api(page, "GET", "overview")).status()).toBe(200);
});
