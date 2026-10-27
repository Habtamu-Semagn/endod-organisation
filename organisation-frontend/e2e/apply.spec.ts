import { expect, test, type Page } from "@playwright/test";
import { API_URL, PLATFORM_KEY } from "./env";
import { PASSWORD, PNG, api, cli, enrolOnPage, passwordStep, uniqueEmail } from "./helpers";

/** A small real PDF (the API checks the first bytes). */
const PDF = Buffer.from("%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n");

const REVIEWER = "reviewer@endod.example";
const TWO_STEP_LATER = "You'll set up two-step verification (Google Authenticator) once your company is approved.";

/** What Endod's super admin does, over endod-bus, straight to the API with the platform key. */
async function platform(page: Page, path: string, data?: unknown) {
  const response = await page.request.fetch(`${API_URL}/platform/${path}`, {
    method: data === undefined ? "GET" : "POST",
    headers: { "X-Platform-Key": PLATFORM_KEY, "Content-Type": "application/json" },
    data: data === undefined ? undefined : JSON.stringify(data),
  });
  expect(response.status(), await response.text()).toBe(200);
  return response.json();
}

test("a company applies with a password, is reviewed by Endod, then enrols and gets the portal", async ({ page }) => {
  const email = uniqueEmail("apply");
  const tin = `99${String(Date.now() % 100_000_000).padStart(8, "0")}`;

  // Apply as a company, from the sign-in page.
  await page.goto("/login");
  await page.getByTestId("apply-link").click();
  await expect(page).toHaveURL(/\/apply$/);
  await expect(page.getByRole("heading", { name: "Apply as a company" })).toBeVisible();
  await page.getByLabel("Company legal name").fill("Abyssinia Textiles PLC");
  await page.getByLabel("Your full name").fill("Meron Alemu");
  await page.getByLabel("Your title").fill("HR Manager");
  await page.getByLabel("Your mobile").fill("0911223344");
  await page.getByLabel("Work email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  await expect(page.getByTestId("two-step-later").filter({ visible: true })).toHaveText(TWO_STEP_LATER);
  await page.getByRole("button", { name: "Create account and continue" }).click();

  // No enrolment while applying: straight on to the company, signed in with the password.
  await expect(page).toHaveURL(/\/apply$/);
  await expect(page.getByRole("heading", { name: "Your company" })).toBeVisible();
  expect((await (await page.request.get("/api/auth/me")).json()).stage).toBe("applicant");
  const enrol = await api(page, "POST", "auth/enroll/start");
  expect(enrol.status()).toBe(409);

  // The company.
  await expect(page.getByRole("heading", { name: "Your company" })).toBeVisible();
  await expect(page.getByLabel("Legal name")).toHaveValue("Abyssinia Textiles PLC");
  await page.getByLabel("Trade name (optional)").fill("Abyssinia Tex");
  await page.getByLabel("TIN", { exact: true }).fill(tin);
  await page.getByLabel("Business license number").fill("AA/14/123456");
  await page.getByLabel("Sector").selectOption("manufacturing");
  await page.getByLabel("Number of employees").fill("240");
  await page.getByLabel("City").fill("Addis Ababa");
  await page.getByLabel("Address").fill("Bole Sub-city, Woreda 3, House 512");
  await page.getByLabel("Company phone").fill("011 551 2345");
  await page.getByLabel("Company email").fill("info@abyssinia-tex.example");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();

  // Saved as it goes: sign out, sign in again, and it carries on at the documents.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  // The password alone, no code.
  await passwordStep(page, email, PASSWORD);
  await expect(page).toHaveURL(/\/apply$/);
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();

  // The documents.
  await page.getByLabel("Trade license").setInputFiles({ name: "trade-license.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(page.getByTestId("document-trade_license")).toContainText("trade-license.pdf uploaded");
  await page.getByLabel("TIN certificate").setInputFiles({ name: "tin.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByTestId("document-tin_certificate")).toContainText("tin.png uploaded");
  await page.getByLabel("Authorization letter").setInputFiles({ name: "letter.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(page.getByTestId("document-authorization_letter")).toContainText("letter.pdf uploaded");
  const view = await page.request.get("/api/application/documents/tin_certificate");
  expect(view.status()).toBe(200);
  expect(view.headers()["content-type"]).toBe("image/png");
  expect(view.headers()["x-content-type-options"]).toBe("nosniff");
  await page.getByRole("button", { name: "Continue to review" }).click();

  // Review and submit.
  const review = page.getByTestId("review-step");
  await expect(review).toContainText(tin);
  await expect(review).toContainText("Manufacturing");
  await expect(review).toContainText("letter.pdf");
  await page.getByRole("button", { name: "Submit application" }).click();
  await expect(page).toHaveURL(/\/under-review$/);
  await expect(page.getByTestId("under-review")).toHaveAttribute("data-status", "submitted");
  await expect(page.getByRole("heading", { name: "Under review" })).toBeVisible();
  await expect(page.getByTestId("two-step-later").filter({ visible: true })).toHaveText(TWO_STEP_LATER);

  // Locked: the portal sends it back here, the API refuses the rest, and the
  // web app never passes the platform API on.
  await page.goto("/");
  await expect(page).toHaveURL(/\/under-review$/);
  const overview = await page.request.get("/api/overview");
  expect(overview.status()).toBe(403);
  expect((await overview.json()).error_code).toBe("APPLICATION_NOT_APPROVED");
  for (const path of ["employees", "claims", "policy", "reports", "organisation"]) {
    expect((await page.request.get(`/api/${path}`)).status()).toBe(403);
  }
  for (const path of ["platform/applications", "platform/organisations", `platform/applications/${"a1".repeat(16)}/approve`]) {
    expect((await page.request.get(`/api/${path}`)).status()).toBe(404);
  }

  // Endod sends it back with a reason; the company fixes it and resubmits.
  const me = await (await page.request.get("/api/auth/me")).json();
  const id = me.organisation.id as string;
  const listed = await platform(page, "applications?status=submitted");
  expect(listed.items.map((item: { id: string }) => item.id)).toContain(id);
  await platform(page, `applications/${id}/reject`, { reason: "The TIN certificate is unreadable.", reviewer: REVIEWER });
  await page.reload();
  await expect(page.getByTestId("under-review")).toHaveAttribute("data-status", "rejected");
  await expect(page.getByTestId("rejection-reason")).toContainText("The TIN certificate is unreadable.");
  await page.getByRole("link", { name: "Edit and resubmit" }).click();
  await expect(page).toHaveURL(/\/apply\?fix=1$/);
  await expect(page.getByTestId("rejection-note")).toContainText("unreadable");
  await expect(page.getByRole("heading", { name: "Review and submit" })).toBeVisible();
  await page.getByTestId("review-step").getByRole("button", { name: "Edit" }).nth(2).click();
  await page.getByLabel("TIN certificate").setInputFiles({ name: "tin-clear.pdf", mimeType: "application/pdf", buffer: PDF });
  await expect(page.getByTestId("document-tin_certificate")).toContainText("tin-clear.pdf uploaded");
  await page.getByRole("button", { name: "Continue to review" }).click();
  await page.getByRole("button", { name: "Submit application" }).click();
  await expect(page).toHaveURL(/\/under-review$/);
  await expect(page.getByTestId("under-review")).toHaveAttribute("data-status", "submitted");

  // Signing in again (the password only) goes straight to the Under review page.
  await page.getByRole("button", { name: "Sign out" }).last().click();
  await expect(page).toHaveURL(/\/login$/);
  await passwordStep(page, email, PASSWORD);
  await expect(page).toHaveURL(/\/under-review$/);
  await expect(page.getByTestId("under-review")).toHaveAttribute("data-status", "submitted");

  // Endod approves it (the version the reviewer looked at): every session of the company ends.
  const detail = await platform(page, `applications/${id}`);
  expect(detail).toMatchObject({ status: "submitted", duplicate_tin: false, email_verified: false });
  await platform(page, `applications/${id}/approve`, { reviewer: REVIEWER, expected_updated_at: detail.updated_at });
  expect((await page.request.get("/api/application")).status()).toBe(401);
  await page.reload();
  await expect(page).toHaveURL(/\/login/);

  // The next sign-in: the password, then two-step verification is mandatory, then the dashboard.
  await passwordStep(page, email, PASSWORD);
  await expect(page).toHaveURL(/\/enroll$/);
  expect((await page.request.get("/api/overview")).status()).toBe(403);
  await enrolOnPage(page);
  await expect(page.getByRole("heading", { name: "Medication Benefit Overview" })).toBeVisible();
  await expect(page.getByTestId("signed-in-organisation").filter({ visible: true })).toContainText("Abyssinia Textiles PLC");
  expect((await page.request.get("/api/overview")).status()).toBe(200);
  const organisations = await platform(page, "organisations");
  expect(organisations.items.find((o: { id: string }) => o.id === id)).toMatchObject({ tin, status: "active", admins: 1 });
});

test("the application refuses a TIN that is in use, with a generic message", async ({ page }) => {
  // An approved organisation (made with the CLI) holds this TIN.
  const tin = `98${String(Date.now() % 100_000_000).padStart(8, "0")}`;
  cli(["create-org", "--name", `TIN Holder ${Date.now()}`, "--tin", tin]);

  await page.goto("/apply");
  await page.getByLabel("Company legal name").fill("Copycat PLC");
  await page.getByLabel("Your full name").fill("Abebe Kebede");
  await page.getByLabel("Your title").fill("Director");
  await page.getByLabel("Your mobile").fill("0922334455");
  await page.getByLabel("Work email").fill(uniqueEmail("copycat"));
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password").fill(PASSWORD);
  await page.getByRole("button", { name: "Create account and continue" }).click();
  await expect(page).toHaveURL(/\/apply$/);
  await expect(page.getByRole("heading", { name: "Your company" })).toBeVisible();
  await page.getByLabel("TIN", { exact: true }).fill(tin);
  await page.getByLabel("Business license number").fill("AA/1/1");
  await page.getByLabel("Sector").selectOption("other");
  await page.getByLabel("Number of employees").fill("5");
  await page.getByLabel("City").fill("Adama");
  await page.getByLabel("Address").fill("Kebele 04");
  await page.getByLabel("Company phone").fill("0221112233");
  await page.getByLabel("Company email").fill("info@copycat.example");
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByTestId("form-error").filter({ visible: true })).toHaveText(
    "This application cannot be accepted with these details. Contact Endod if you think this is a mistake."
  );
});
