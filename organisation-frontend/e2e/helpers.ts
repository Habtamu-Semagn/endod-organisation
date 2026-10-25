import { createHmac } from "node:crypto";
import { execFileSync } from "node:child_process";
import { expect, type Page } from "@playwright/test";
import { WEB_ORIGIN, apiEnv, backendDir, python } from "./env";

// --- TOTP (RFC 6238, as Google Authenticator computes it) ---------------------------------

function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.replace(/[\s=]/g, "").toUpperCase();
  let bits = 0;
  let value = 0;
  const out: number[] = [];
  for (const char of clean) {
    const index = alphabet.indexOf(char);
    if (index < 0) throw new Error(`not base32: ${char}`);
    value = (value << 5) | index;
    bits += 5;
    if (bits >= 8) {
      out.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(out);
}

export function totpAt(secret: string, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", base32Decode(secret)).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const binary =
    ((digest[offset] & 0x7f) << 24) | (digest[offset + 1] << 16) | (digest[offset + 2] << 8) | digest[offset + 3];
  return String(binary % 1_000_000).padStart(6, "0");
}

export const currentStep = () => Math.floor(Date.now() / 1000 / 30);

/** An admin's authenticator: each code is accepted once, so it tracks the last step used. */
export class Authenticator {
  constructor(
    readonly secret: string,
    public lastStep: number
  ) {}

  /** A code the API will accept now: newer than the last one, within one step of now. */
  async next(): Promise<string> {
    const wanted = this.lastStep + 1;
    while (wanted > currentStep() + 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    const step = Math.max(wanted, currentStep());
    this.lastStep = step;
    return totpAt(this.secret, step);
  }
}

// --- the CLI (what Endod runs to set up an organisation) ------------------------------------

export function cli(args: string[], stdin = ""): string {
  return execFileSync(python, ["-m", "app.cli", ...args], {
    cwd: backendDir,
    env: { ...process.env, ...apiEnv },
    input: stdin,
    encoding: "utf-8",
  });
}

let counter = 0;
function unique(): string {
  counter += 1;
  return `${Date.now().toString(36)}${counter}`;
}

export function uniqueEmail(prefix: string): string {
  return `${prefix}-${unique()}@tena.example`;
}

export function createOrg(name = "Tena Logistics PLC"): string {
  counter += 1;
  const tin = String((Date.now() % 1_000_000_000) * 10 + (counter % 10)).padStart(10, "0");
  const out = cli(["create-org", "--name", `${name} ${unique()}`, "--tin", tin]);
  const id = out.trim().split(/\r?\n/).pop() ?? "";
  expect(id).toMatch(/^[0-9a-f]{32}$/);
  return id;
}

export const PASSWORD = "a long e2e passphrase";

/** An admin with a password (read from stdin) who still has to enrol through the printed setup link. */
export function createAdmin(org: string, prefix: string, name = "Selam Tesfaye") {
  const email = uniqueEmail(prefix);
  const out = cli(["create-admin", "--org", org, "--email", email, "--name", name, "--password-stdin"], `${PASSWORD}\n`);
  expect(out).not.toContain(PASSWORD);
  const link = out.trim().split(/\r?\n/).pop() ?? "";
  expect(link).toMatch(/\/setup#[A-Za-z0-9_-]{40,}$/);
  return { email, password: PASSWORD, name, link, org };
}

/** An admin created without a password: returns the one-time setup link. */
export function createAdminWithLink(org: string, prefix: string, name: string) {
  const email = uniqueEmail(prefix);
  const out = cli(["create-admin", "--org", org, "--email", email, "--name", name]);
  const link = out.trim().split(/\r?\n/).pop() ?? "";
  expect(link).toMatch(/\/setup#[A-Za-z0-9_-]{40,}$/);
  return { email, link };
}

// --- the browser -------------------------------------------------------------------------------

export async function passwordStep(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

/** On the enrolment page: read the key, confirm a code, accept the recovery codes. */
export async function enrolOnPage(page: Page): Promise<{ auth: Authenticator; recoveryCodes: string[] }> {
  await expect(page).toHaveURL(/\/enroll$/);
  await expect(page.getByTestId("totp-qr").filter({ visible: true })).toBeVisible();
  const secret = ((await page.getByTestId("totp-secret").filter({ visible: true }).textContent()) ?? "").replace(/\s/g, "");
  expect(secret).toMatch(/^[A-Z2-7]{32}$/);
  const step = currentStep();
  await page.getByLabel("Code from the app").fill(totpAt(secret, step));
  await page.getByRole("button", { name: "Confirm and continue" }).click();
  await expect(page.getByTestId("recovery-code").filter({ visible: true })).toHaveCount(10);
  const recoveryCodes = await page.getByTestId("recovery-code").filter({ visible: true }).allTextContents();
  await page.getByLabel("I have saved my recovery codes").check();
  await page.getByRole("button", { name: "Continue to the portal" }).click();
  await expect(page).toHaveURL(new RegExp(`^${WEB_ORIGIN}/$`));
  return { auth: new Authenticator(secret, step), recoveryCodes };
}

/** A new organisation and its admin, signed in and enrolled through the pages. */
export async function signedInAdmin(page: Page, prefix: string, org = createOrg()) {
  const admin = createAdmin(org, prefix);
  await page.goto(admin.link);
  await page.getByLabel("Your password").fill(admin.password);
  await page.getByRole("button", { name: "Continue" }).click();
  const { auth } = await enrolOnPage(page);
  await expect(page.getByTestId("signed-in-name").filter({ visible: true })).toHaveText(admin.name);
  return { ...admin, auth };
}

/** Answers the re-authentication prompt with a fresh code. */
export async function reauthenticate(page: Page, auth: Authenticator) {
  const dialog = page.getByTestId("reauth-dialog").filter({ visible: true });
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Authenticator code").fill(await auth.next());
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(dialog).toBeHidden();
}

/** A call to this site's BFF with the page's session (as the page's own scripts make it). */
export async function api(page: Page, method: "GET" | "POST" | "PUT" | "PATCH", path: string, data?: unknown) {
  const response = await page.request.fetch(`/api/${path}`, {
    method,
    headers: { Origin: WEB_ORIGIN, "Content-Type": "application/json" },
    data: data === undefined ? undefined : JSON.stringify(data),
  });
  return response;
}

export async function addEmployee(page: Page, fields: Record<string, string>) {
  const response = await api(page, "POST", "employees", {
    employee_number: `ET-${unique()}`,
    phone: "0911223344",
    department: "Engineering",
    payout_method: "cbe",
    payout_account: "1000123456789",
    ...fields,
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as { id: string; name: string; employee_number: string };
}

/** A 1x1 PNG: a real image, as a phone camera would send (smaller). */
export const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64"
);

/** Through the New Claim page: one medicine, a receipt photo. Leaves the browser on the claim. */
export async function enterClaim(
  page: Page,
  employeeName: string,
  { receipt, medicine = "Metformin 500mg", quantity = "2", price = "250.50" }: { receipt: string; medicine?: string; quantity?: string; price?: string }
) {
  await page.goto("/claims/new");
  await page.getByLabel("Find employee").fill(employeeName);
  await page.getByTestId("employee-option").filter({ hasText: employeeName }).click();
  await expect(page.getByTestId("employee-remaining").filter({ visible: true })).toBeVisible();
  await page.getByLabel("Pharmacy name").fill("Kenema Pharmacy Bole");
  await page.getByLabel("Pharmacy TIN").fill("0012345678");
  await page.getByLabel("Receipt number").fill(receipt);
  await page.getByLabel("Medicine 1").fill(medicine);
  await page.getByLabel("Quantity 1").fill(quantity);
  await page.getByLabel("Unit price (ETB) 1").fill(price);
  await page.getByLabel(/Receipt file/).setInputFiles({ name: "receipt.png", mimeType: "image/png", buffer: PNG });
  await expect(page.getByTestId("receipt-uploaded").filter({ visible: true })).toContainText("receipt.png attached");
  await page.getByRole("button", { name: "Save claim" }).click();
  await expect(page).toHaveURL(/\/claims\/[0-9a-f]{32}$/);
  await expect(page.getByTestId("claim-status").filter({ visible: true })).toHaveText("Pending");
}
