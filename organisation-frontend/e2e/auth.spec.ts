import { expect, test } from "@playwright/test";
import { createAdminWithLink, createOrg, enrolOnPage, passwordStep } from "./helpers";

test("pages redirect to the sign-in when signed out", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  for (const path of ["/claims", "/employees", "/payments", "/reports", "/settings", `/claims/${"a1".repeat(16)}`]) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`/login\\?next=${encodeURIComponent(path).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  }
  // The BFF refuses API calls, files and exports without a session.
  expect((await page.request.get("/api/overview")).status()).toBe(401);
  expect((await page.request.get(`/api/receipts/${"a1".repeat(16)}`)).status()).toBe(401);
  expect((await page.request.get("/api/export/employees/export")).status()).toBe(401);
  // Paths outside the allowlist do not exist.
  expect((await page.request.get("/api/organisations")).status()).toBe(404);
  expect((await page.request.get("/api/export/passwords")).status()).toBe(404);
});

test("enrol through the setup link, then sign in with a TOTP code", async ({ page, context }) => {
  const org = createOrg("Awash Breweries");
  const { email, link } = createAdminWithLink(org, "setup", "Hana Girma");
  await page.goto(link);
  await expect(page.getByTestId("setup-name").filter({ visible: true })).toHaveText("Hana Girma");
  await expect(page).toHaveURL(/\/setup$/);
  await page.getByLabel("New password").fill("password1");
  await page.getByLabel("Repeat the password").fill("password1");
  await page.getByRole("button", { name: "Set password and continue" }).click();
  await expect(page.getByTestId("form-error").filter({ visible: true })).toContainText("too common");
  await page.getByLabel("New password").fill("kebele seven blue door");
  await page.getByLabel("Repeat the password").fill("kebele seven blue door");
  await page.getByRole("button", { name: "Set password and continue" }).click();
  const { auth, recoveryCodes } = await enrolOnPage(page);
  expect(new Set(recoveryCodes).size).toBe(10);
  await expect(page.getByTestId("signed-in-name").filter({ visible: true })).toHaveText("Hana Girma");
  await expect(page.getByTestId("signed-in-organisation").filter({ visible: true })).toContainText("Awash Breweries");

  // The session is an httpOnly, SameSite=Strict cookie the page cannot read.
  const cookie = (await context.cookies()).find((c) => c.name.endsWith("tenacare_org"));
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(await page.evaluate(() => document.cookie)).not.toContain("tenacare_org");
  expect(JSON.stringify(await (await page.request.get("/api/auth/me")).json())).not.toMatch(/token/);

  // The link worked once.
  const reuse = await context.newPage();
  await reuse.goto(link);
  await expect(reuse.getByTestId("form-error").filter({ visible: true })).toContainText("invalid or has expired");
  await reuse.close();

  // Sign out, then sign in: password, then a new code.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await passwordStep(page, email, "kebele seven blue door");
  await expect(page.getByRole("heading", { name: "Two-step verification" })).toBeVisible();
  await page.getByLabel("Authentication code").fill("000000");
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByTestId("form-error").filter({ visible: true })).toContainText("not valid");
  await page.getByLabel("Authentication code").fill(await auth.next());
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("heading", { name: "Medication Benefit Overview" })).toBeVisible();
  await expect(page.getByTestId("kpi-claims").filter({ visible: true })).toHaveText("0");
});

test("cross-site requests are refused", async ({ page }) => {
  const evil = await page.request.post("/api/auth/login", {
    headers: { Origin: "https://evil.example", "Content-Type": "application/json" },
    data: { email: "x@tena.example", password: "whatever-1" },
  });
  expect(evil.status()).toBe(403);
  const noOrigin = await page.request.post("/api/auth/login", {
    headers: { "Content-Type": "application/json" },
    data: { email: "x@tena.example", password: "whatever-1" },
  });
  expect(noOrigin.status()).toBe(403);
  const upload = await page.request.post("/api/receipts", {
    headers: { Origin: "https://evil.example", "Content-Type": "image/png" },
    data: Buffer.from("x"),
  });
  expect(upload.status()).toBe(403);
  const html = await page.request.get("/login");
  expect(html.headers()["x-frame-options"]).toBe("DENY");
});
