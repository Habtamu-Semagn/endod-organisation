# Company onboarding: TenaCare applications reviewed in the Endod admin

Companies apply themselves on TenaCare (organisation.endod-health.com). Endod
reviews them in the super admin (admin.endod-health.com). No demo booking.

## Application (TenaCare, public)

States: `draft` -> `submitted` -> `approved` | `rejected` (a rejected
application can be edited and resubmitted -> `submitted`). An organisation
created this way stays inactive (its admins see only the application / Under
review page) until approved; organisations created by the CLI are approved.

Fields
- company: legal_name, trade_name (optional), tin (10 digits), business_license_number,
  sector (closed list: government, ngo, manufacturing, services, finance, telecom,
  health, education, retail, transport, agriculture, other), employee_count (int >= 1),
  city, address, phone (Ethiopian number), email.
- contact (the applicant = the first OrgAdmin): full_name, title, phone (Ethiopian mobile),
  email (sign-in), password; TOTP enrolment is required before the wizard continues.
- documents (all required): trade_license, tin_certificate, authorization_letter.
  PDF/JPEG/PNG/WebP, magic-byte checked, at most 10 MB each.

## TenaCare platform API (for the super admin)

Served by the TenaCare API, which joins the external `endod-bus` network with
alias `endod-organisation-api` (port 8000). Every route requires header
`X-Platform-Key` equal to env `ORG_PLATFORM_KEY` (constant-time; 503 when unset);
these routes are never reachable through the TenaCare web BFF, and they do not
require X-BFF-Secret.

- `GET /platform/applications?status=submitted|draft|approved|rejected`
  -> `{"items": [{"id", "legal_name", "trade_name", "tin", "sector", "employee_count",
  "city", "status", "submitted_at", "updated_at", "contact": {"full_name", "title",
  "phone", "email"}}]}` (newest first)
- `GET /platform/applications/{id}` -> one item as above plus `business_license_number`,
  `address`, `phone`, `email`, `rejection_reason`, `reviewed_at`,
  `documents: [{"kind", "filename", "content_type", "size", "uploaded_at"}]`
- `GET /platform/applications/{id}/documents/{kind}` -> the file, streamed
  (Content-Type from the stored type, `Content-Disposition: attachment`, `nosniff`)
- `POST /platform/applications/{id}/approve` -> 200 `{"status": "approved"}`;
  409 `{"detail": "..."}` unless status is `submitted`.
  Body `{"reviewer": "<admin email>"}` (recorded in TenaCare's audit).
- `POST /platform/applications/{id}/reject` body `{"reason": str (3-1000), "reviewer"}`
  -> 200; 409 unless `submitted`. The reason is shown to the applicant.
- `GET /platform/organisations` -> `{"items": [{"id", "name", "tin", "status": "active"|"suspended",
  "created_at", "employees": int, "admins": int}]}`
- `POST /platform/organisations/{id}/suspend` / `.../reactivate` body `{"reviewer"}`.
  A suspended organisation's admins are signed out and refused (generic message).

ids are 32-char lowercase hex. Unknown ids -> 404.

## Super admin

- Env `ORGANISATION_API_URL` (default `http://endod-organisation-api:8000`) and
  `ORGANISATION_PLATFORM_KEY` (same value as TenaCare's ORG_PLATFORM_KEY), API container only.
- Verifications: a Hospitals | Companies switch; Companies lists applications with
  detail, documents, Approve and Reject with reason (fresh TOTP re-auth, audited).
- A Companies directory (or a tab in Organisations): list, suspend, reactivate (re-auth, audited).
