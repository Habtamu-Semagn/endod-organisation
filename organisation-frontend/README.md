# TenaCare web app

The Next.js 16 front end of the TenaCare employer portal (design by Habtamu Semagn).
See the [repository README](../README.md) for what it does and how it is secured.

- `app/(dashboard)/`: Overview, Claims (list, new, detail), Payments, Employees, Reports, Policy & Settings
- `app/login`, `app/setup`, `app/enroll`: sign-in, the one-time setup link, authenticator enrolment
- `app/api/`: the BFF. The browser talks only to it; it keeps the session in an httpOnly
  cookie and calls the organisation API with `X-BFF-Secret` (allowlisted paths only)
- `lib/format.ts`: money as integer santim, shown and parsed without floats
- `e2e/`: Playwright tests against the real API (`npx next build && npx playwright test`)

```sh
npm ci
npm run dev   # ORG_API_URL defaults to http://127.0.0.1:8040
```
