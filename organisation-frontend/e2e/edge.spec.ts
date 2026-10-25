import { expect, test } from "@playwright/test";
import { EDGE_SECRET, WEB_ORIGIN } from "./env";

test("only requests carrying nginx's edge key are served", async ({ playwright }) => {
  // Another container on the shared edge network, without the key.
  const direct = await playwright.request.newContext({ baseURL: WEB_ORIGIN, extraHTTPHeaders: {} });
  for (const path of ["/login", "/", "/api/auth/me", "/api/overview", "/_next/static/missing.js", "/endod_logo.jpeg"]) {
    const resp = await direct.get(path, { maxRedirects: 0 });
    expect(resp.status(), path).toBe(403);
  }
  const forged = await direct.post("/api/auth/login", {
    headers: { Origin: WEB_ORIGIN, "Content-Type": "application/json", "X-Endod-Client-IP": "203.0.113.9" },
    data: { email: "x@tena.example", password: "whatever-1" },
  });
  expect(forged.status()).toBe(403);
  const wrong = await direct.get("/login", { headers: { "X-Endod-Edge-Key": `${EDGE_SECRET.slice(0, -1)}x` } });
  expect(wrong.status()).toBe(403);
  // The container's own health check (on localhost) needs no key, and says nothing else.
  const health = await direct.get("/api/health");
  expect(health.status()).toBe(200);
  expect(await health.json()).toEqual({ status: "ok" });
  await direct.dispose();

  // With the key (as nginx sends it), the site works.
  const viaNginx = await playwright.request.newContext({ baseURL: WEB_ORIGIN, extraHTTPHeaders: { "X-Endod-Edge-Key": EDGE_SECRET } });
  expect((await viaNginx.get("/login")).status()).toBe(200);
  await viaNginx.dispose();
});
