import { expect, test, type Page } from "@playwright/test";
import { API_URL, WEB_ORIGIN } from "./env";
import { PASSWORD, api, passwordStep, reauthenticate, signedInAdmin, uniqueEmail, type Authenticator } from "./helpers";

// "Connect your system": the company's own systems and the integration API.

const INTEGRATIONS = `${API_URL}/integrations/v1`;

function basic(clientId: string, secret: string) {
  return { Authorization: `Basic ${Buffer.from(`${clientId}:${secret}`).toString("base64")}` };
}

/** The 3 steps, with the fresh code asked for (a new admin). Leaves the browser on step 3; returns the client ID and secret. */
async function connectSystem(page: Page, auth: Authenticator, name: string, abilities: string[], mode: "Live" | "Test" = "Live") {
  await page.goto("/connect");
  await page.getByRole("button", { name: "Connect a system" }).click();
  const flow = page.getByRole("dialog", { name: "Connect a system" });
  await expect(flow.getByTestId("connect-step")).toHaveText("Step 1 of 3");
  await flow.getByLabel("What is the system called?").fill(name);
  await flow.getByRole("button", { name: "Next" }).click();
  await expect(flow.getByTestId("connect-step")).toHaveText("Step 2 of 3");
  for (const ability of abilities) await flow.getByText(ability, { exact: true }).click();
  await flow.getByText(mode, { exact: true }).click();
  await flow.getByRole("button", { name: "Connect" }).click();
  // A fresh code from the authenticator (each test signs in a new admin: none was given yet).
  await reauthenticate(page, auth);
  const done = page.getByTestId("connect-done");
  await expect(page.getByTestId("connect-step")).toHaveText("Step 3 of 3");
  await expect(done).toContainText("Save the secret now");
  const clientId = (await done.getByTestId("client-id").textContent()) ?? "";
  const secret = (await done.getByTestId("client-secret").textContent()) ?? "";
  return { clientId, secret, done };
}

async function token(page: Page, clientId: string, secret: string, scope?: string) {
  return page.request.post(`${INTEGRATIONS}/oauth/token`, {
    form: { grant_type: "client_credentials", ...(scope ? { scope } : {}) },
    headers: basic(clientId, secret),
  });
}

test("an admin connects a system in 3 steps with a fresh code; the secret is shown once", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "connect");
  await page.getByRole("link", { name: "Connect your system" }).click();
  await expect(page).toHaveURL(/\/connect$/);
  await expect(page.getByTestId("no-connections")).toBeVisible();
  await expect(page.getByRole("link", { name: "Developer guide" })).toHaveAttribute("href", /\/organisation\/v1\/docs$/);

  // The fresh code is asked for before anything is connected.
  await page.getByRole("button", { name: "Connect a system" }).click();
  const flow = page.getByRole("dialog", { name: "Connect a system" });
  await flow.getByLabel("What is the system called?").fill("Payroll system");
  await flow.getByRole("button", { name: "Next" }).click();
  await flow.getByText("Sync employees from your HR system", { exact: true }).click();
  await flow.getByText("See claims and their status", { exact: true }).click();
  await flow.getByRole("button", { name: "Connect" }).click();
  await reauthenticate(page, auth);

  const done = page.getByTestId("connect-done");
  await expect(page.getByTestId("connect-step")).toHaveText("Step 3 of 3");
  await expect(done).toContainText("Save the secret now");
  const clientId = (await done.getByTestId("client-id").textContent()) ?? "";
  const secret = (await done.getByTestId("client-secret").textContent()) ?? "";
  expect(clientId).toMatch(/^endod_live_[0-9a-f]{24}$/);
  expect(secret.length).toBeGreaterThanOrEqual(40);
  await expect(done.getByRole("button", { name: "Copy Client secret" })).toBeVisible();

  // The printable setup guide: the details, never the secret.
  const link = done.getByRole("link", { name: "Download setup guide" });
  await expect(link).toHaveAttribute("href", /^\/setup-guide\/[0-9a-f]{32}$/);
  const guide = await page.context().newPage();
  await guide.goto((await link.getAttribute("href")) ?? "");
  await expect(guide.getByTestId("setup-guide")).toContainText(clientId);
  await expect(guide.getByTestId("setup-guide")).toContainText("/oauth/token");
  await expect(guide.getByTestId("setup-guide")).toContainText("employees.write");
  expect(await guide.content()).not.toContain(secret);
  await guide.close();

  await page.getByRole("button", { name: "I saved the secret" }).click();
  const card = page.getByTestId("connection").filter({ hasText: "Payroll system" });
  await expect(card).toContainText("Sync employees from your HR system");
  await expect(card).toContainText("See claims and their status");
  await expect(card.getByTestId("mode-badge")).toHaveText("Live");
  await expect(card.getByTestId("last-used")).toHaveText("Not used yet");
  // Shown once: never again, on the page or from the API.
  expect(await page.content()).not.toContain(secret);
  expect(await (await api(page, "GET", "connections")).text()).not.toContain(secret);
  // No jargon on the main page.
  const main = (await page.locator("main").innerText()).toLowerCase();
  for (const word of ["oauth", "scope", "webhook", "client id", "secret"]) expect(main).not.toContain(word);

  // The system's side: a token works.
  expect((await token(page, clientId, secret)).status()).toBe(200);
});

test("disconnecting asks for confirmation and a fresh code, and stops the system", async ({ page }) => {
  const admin = await signedInAdmin(page, "disconnect");
  const { clientId, secret } = await connectSystem(page, admin.auth, "Old payroll", ["See payments"]);
  await page.getByRole("button", { name: "I saved the secret" }).click();

  // A new sign-in: the code given while connecting no longer counts.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await passwordStep(page, admin.email, admin.password);
  await page.getByLabel("Authentication code").fill(await admin.auth.next());
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByTestId("signed-in-name").filter({ visible: true })).toHaveText(admin.name);

  await page.goto("/connect");
  const card = page.getByTestId("connection").filter({ hasText: "Old payroll" });
  await card.getByRole("button", { name: "Disconnect" }).click();
  const confirm = page.getByTestId("disconnect-dialog");
  await expect(confirm).toContainText("It stops working immediately");
  // Cancelling keeps it.
  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Disconnect" }).click();
  await confirm.getByRole("button", { name: "Disconnect" }).click();
  await reauthenticate(page, admin.auth);
  await expect(page.getByTestId("success-banner").filter({ visible: true })).toHaveText("Old payroll is disconnected.");
  await expect(card).toHaveCount(0);
  expect((await token(page, clientId, secret)).status()).toBe(401);
});

test("the Advanced panel: IP restriction, webhook with a test event, request log, secret rotation", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "advanced");
  const { clientId, secret } = await connectSystem(page, auth, "HR system", ["See employee list"], "Test");
  await page.getByRole("button", { name: "I saved the secret" }).click();
  const card = page.getByTestId("connection").filter({ hasText: "HR system" });
  await expect(card.getByTestId("mode-badge")).toHaveText("Test");

  // A token from the system's side: then it shows as used, in the request log.
  expect((await token(page, clientId, secret)).status()).toBe(200);
  await page.reload();
  await expect(card.getByTestId("last-used")).toHaveText(/Last used/);
  await card.getByRole("button", { name: "Advanced" }).click();
  const advanced = card.getByTestId("advanced");
  await expect(advanced.getByTestId("request-log")).toContainText("POST /integrations/v1/oauth/token");

  // Changes need a fresh code (still fresh from connecting: no prompt within 10 minutes).
  await advanced.getByLabel("Allowed IP addresses").fill("196.188.10.0/24\n127.0.0.1");
  await advanced.getByRole("button", { name: "Save addresses" }).click();
  await expect(advanced.getByTestId("success-banner")).toHaveText("IP restriction saved.");
  await expect(advanced.getByLabel("Allowed IP addresses")).toHaveValue("196.188.10.0/24\n127.0.0.1");

  await advanced.getByLabel("Webhook URL").fill("https://hooks.example.com/endod");
  await advanced.getByRole("button", { name: "Save webhook" }).click();
  await expect(page.getByTestId("revealed-secret")).toContainText("whsec_");
  await page.getByRole("button", { name: "I saved it" }).click();
  await expect(card).toContainText("Get notified when claims are approved or paid");

  await advanced.getByRole("button", { name: "Send test event" }).click();
  await expect(advanced.getByTestId("delivery-log")).toContainText("endpoint.test");

  // Rotating the secret: confirmed, shown once, and the old one stops.
  await advanced.getByRole("button", { name: "Rotate secret" }).click();
  await page.getByTestId("rotate-dialog").getByRole("button", { name: "Make a new secret" }).click();
  const fresh = (await page.getByTestId("revealed-secret").textContent()) ?? "";
  expect(fresh).not.toBe(secret);
  await page.getByRole("button", { name: "I saved it" }).click();
  expect((await token(page, clientId, secret)).status()).toBe(401);
  expect((await token(page, clientId, fresh)).status()).toBe(200);
});

test("an organisation that is not approved does not get the page", async ({ page }) => {
  // A company still applying: signed in with its password only, sent to its application.
  const started = await page.request.post("/api/application/start", {
    headers: { Origin: WEB_ORIGIN, "Content-Type": "application/json" },
    data: JSON.stringify({
      legal_name: "Pending Company PLC",
      full_name: "Meron Alemu",
      title: "HR Manager",
      phone: "0911223344",
      email: uniqueEmail("pending"),
      password: PASSWORD,
    }),
  });
  expect(started.status(), await started.text()).toBe(200);
  await page.goto("/connect");
  await expect(page).toHaveURL(/\/apply$/);
  await expect(page.getByRole("link", { name: "Connect your system" })).toHaveCount(0);
  expect((await api(page, "GET", "connections")).status()).toBe(403);
  expect((await api(page, "POST", "connections", { name: "Sneaky", scopes: ["employees.read"] })).status()).toBe(403);
});

test("end to end: a token, employees synced from the HR system, and they appear in the Employees screen", async ({ page }) => {
  const { auth } = await signedInAdmin(page, "e2e-sync");
  const { clientId, secret } = await connectSystem(page, auth, "Payroll sync", ["Sync employees from your HR system"]);
  await page.getByRole("button", { name: "I saved the secret" }).click();

  // The company's system, as curl would: a token, then the employees.
  const tokenResponse = await token(page, clientId, secret, "employees.write");
  expect(tokenResponse.status(), await tokenResponse.text()).toBe(200);
  const { access_token: accessToken, expires_in: expiresIn } = await tokenResponse.json();
  expect(expiresIn).toBe(300);
  const employees = [
    { employee_number: "HR-E2E-1", name: "Hana Synced", phone: "0911000101", department: "Payroll" },
    {
      employee_number: "HR-E2E-2",
      name: "Dawit Synced",
      phone: "0911000102",
      department: "Payroll",
      payout_method: "cbe",
      payout_account: "1000200030004",
      dependants: [{ name: "Ruth Dawit", relationship: "child", birth_date: "2018-05-01" }],
    },
  ];
  const sync = (key: string) =>
    page.request.post(`${INTEGRATIONS}/employees`, {
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json", "Idempotency-Key": key },
      data: JSON.stringify({ employees }),
    });
  const first = await sync("e2e-sync-1");
  expect(first.status(), await first.text()).toBe(200);
  expect((await first.json()).summary).toEqual({ create: 2, update: 0, unchanged: 0, error: 0 });
  // Sent again (a nightly sync): nothing changes.
  const again = await sync("e2e-sync-2");
  expect((await again.json()).summary).toEqual({ create: 0, update: 0, unchanged: 2, error: 0 });

  await page.goto("/employees");
  const rows = page.getByTestId("employee-row").filter({ visible: true });
  await expect(rows).toHaveCount(2);
  await expect(rows.filter({ hasText: "Hana Synced" })).toContainText("HR-E2E-1");
  await expect(rows.filter({ hasText: "Dawit Synced" })).toContainText("HR-E2E-2");
});
