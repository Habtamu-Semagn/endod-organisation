import fs from "node:fs";
import os from "node:os";
import path from "node:path";

/** Settings shared by playwright.config.ts and the specs. */

export const API_PORT = 8140;
export const WEB_PORT = 3240;
export const API_URL = `http://127.0.0.1:${API_PORT}`;
export const WEB_ORIGIN = `http://localhost:${WEB_PORT}`;
export const BFF_SECRET = "e2e-bff-secret-0123456789abcdefghijklmnop";

export const backendDir = path.join(__dirname, "..", "..", "backend");
// The backend's Python: E2E_PYTHON (CI), else backend/.venv.
export const python =
  process.env.E2E_PYTHON ??
  path.join(backendDir, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

// A fresh database and receipts directory per run. Set once in the main
// process (which also clears earlier runs' files); test workers inherit them.
if (!process.env.E2E_DB) {
  for (const name of fs.readdirSync(os.tmpdir())) {
    if (name.startsWith("tenacare-e2e-")) fs.rmSync(path.join(os.tmpdir(), name), { force: true, recursive: true });
  }
  const stamp = Date.now();
  process.env.E2E_DB = path.join(os.tmpdir(), `tenacare-e2e-${stamp}.db`).replace(/\\/g, "/");
  process.env.E2E_RECEIPTS = path.join(os.tmpdir(), `tenacare-e2e-receipts-${stamp}`);
}

/** The portal API's settings for the run (the CLI runs with them too). */
export const apiEnv: Record<string, string> = {
  ORG_ENVIRONMENT: "development",
  ORG_DATABASE_URL: `sqlite:///${process.env.E2E_DB}`,
  ORG_RECEIPTS_DIR: process.env.E2E_RECEIPTS ?? "",
  SESSION_SECRET: "e2e-session-secret-0123456789abcdefghijklmnop",
  SITE_ORIGIN: WEB_ORIGIN,
  BFF_SHARED_SECRET: BFF_SECRET,
  // The browser tests all come from 127.0.0.1; the per-address limit is tested in pytest.
  ORG_IP_FAILURE_LIMIT: "100",
  PYTHONUNBUFFERED: "1",
};
