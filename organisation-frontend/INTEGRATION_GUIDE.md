# Integration Guide: TenaCare Organisation Portal × DEDAN Health × Hospital Portal

> Companion analysis for `/home/hab/Desktop/endod-organisation/organisation-frontend`.
> Source projects analysed:
> - `/home/hab/Desktop/dedan-health` (patient-facing health navigation + insurance design)
> - `/home/hab/Desktop/dedan-hospital-portal` (hospital EMR/operations backend + portal)

## 1. What each project is

### 1.1 organisation-frontend (this repo) — "TenaCare Benefits SaaS"
- Next.js 16 / React 19 / Tailwind v4 employer-facing portal.
- Audience: HR/Benefits admins of a corporate employer (e.g. EthioTelecom Corp).
- Pages: Overview (medication spend KPIs), Claims (verify prescription receipts), Payments (batch disbursement to CBE/Telebirr), Employees (roster, eligibility, dependent coverage, per-employee limits).
- Currency: ETB. Settlement rails: CBE, Awash, Dashen, Telebirr.
- State today: purely presentational — hardcoded mock data, no backend, no auth, no API calls. The claims page already models the full verification UX (approve/reject, receipt image, pharmacy, TIN, rejection reasons).

### 1.2 dedan-health — "DEDAN Health" (patient platform)
- FastAPI (backend-v2/) + Next.js patient portal + mobile + WhatsApp/SMS.
- Capabilities: AI symptom triage, partner hospital directory & booking, digital health card (DE###### + QR verify), wallet (Chapa deposits, santim), appointments/reminders, medical records, inbox/notifications, consent.
- Insurance design doc (INSURANCE_TENA_MEDHIN_README.md): CBHI/SHI/medhinLink profiles, coverage (negative list), cashless booking path, InsuranceClaim model, premium enrolment.
- Auth: none today (production blocker).

### 1.3 dedan-hospital-portal — "Endod Hospital Service"
- FastAPI hospital EMR: patients, doctors, departments, queues, bookings, visits, clinical records & files, imports (FHIR/CSV), onboarding, auth (staff roles).
- Payer model already exists: Payer = cash | cbhi | private | credit — where credit = "Employer or government credit agreement." This is the hook for organisation coverage.
- Links patients to Endod accounts via dedan_id (health card QR). Roles include billing, pharmacist, records.
- Storage: SQLite/Postgres via SQLAlchemy + Alembic.
## 2. The integration opportunity in one sentence

Turn TenaCare from a manual receipt-keying tool into the automated financial layer between employers, hospitals/pharmacies and (optionally) public insurance: receipts stop being uploaded PDFs and become verified digital claims that flow from the hospital portal's patient history, are matched to the employer's employee roster, checked against benefit policy + insurance coverage, approved in one click, and settled in a batch to pharmacies.

That is the "feature on top" that generates new profit (see section 5).

## 3. Integration architecture (how to connect easily)

### 3.1 Identity bridge (do this first)
- Single canonical patient/employee key = dedan_id (DE######).
- organisation-frontend Employees page already has an employee roster. Add a dedan_id column (and phone) to each employee. The hospital portal already links a Patient to a dedan_id (/patients/{id}/link), and dedan-health issues the card.
- Linking flow: HR imports employees (CSV/HRIS) -> system calls dedan-health/hospital portal to match by phone -> stores dedan_id -> employee's card becomes verifiable at any hospital desk.
- Why easy: both projects already speak dedan_id; no new identity system needed.

### 3.2 Receipts flow (the core ask)
Today: employee pays cash at pharmacy -> uploads stamped receipt photo -> HR manually verifies -> pays.

Target (automated):

1. Source of truth for the receipt: hospital portal.
   - Pharmacist dispenses -> creates a ClinicalRecord (category prescription/document) with dispensed medicines, quantities, unit prices, total, pharmacy TIN, receipt file.
   - Or hospital bills an OPD visit -> invoice record.
   - These records are already publishable to Endod ("published to Endod like any other" in imports).
2. Trigger: hospital portal emits an event/webhook prescription.dispensed (or visit.completed) containing {patient_dedan_id, hospital_id, invoice_id, total_santim, items[], file_id}.
3. Ingestion in TenaCare: a new backend (see 3.4) receives the webhook, matches patient_dedan_id -> employee -> organisation, creates a Claim (status pending_verification) with the receipt file attached.
4. HR verification UI: the existing Claims page renders the claim (already has approve/reject + rejection reasons). Approve -> status approved -> enters the payment batch.
5. Settlement: existing Payments page batches approved claims and disburses to the pharmacy's bank/Telebirr; on success calls hospital portal mark invoice paid (or records a settlement reference).

Fallback for pharmacies not on the portal: keep the manual upload path (current UI) but require a stamped receipt + TIN — exactly what the current claims page already captures.

### 3.3 Coverage / eligibility check (reuse dedan-health insurance + org policy)
Before approving a claim, TenaCare should answer: "Is this medication covered, and how much?"

- Organisation policy layer (new, small): per-employer benefit rules — annual cap per employee, dependent coverage, excluded drug classes, copay %, pharmacy network. Store in TenaCare backend.
- Insurance layer (dedan-health): if the employee also has CBHI/SHI/medhinLink, dedan-health's Coverage Service (negative list) says whether the medicine is on the 500+ essential list and the insurer's share. TenaCare then computes: org_share = total - insurer_share - employee_copay, never exceeding the annual cap.
- Net effect: org only pays what insurance doesn't — direct cost saving -> the "profit" lever (section 5).

### 3.4 Minimal backend you must add (TenaCare has none today)
TenaCare is frontend-only. To integrate it needs a small backend (FastAPI, matching the other two projects' stack):

- Employee (roster, dedan_id, benefit policy, annual spend)
- Claim (employee, source hospital/pharmacy, invoice_id, items, amount, status, receipt file ref, settlement ref)
- BenefitPolicy (employer rules)
- Webhook receiver for hospital portal events
- Auth (reuse hospital portal's staff/JWT pattern; add employer-admin role)
- Audit log (hospital portal already has audit() — copy the pattern)

Recommended: do not merge codebases. Keep three services + an API gateway/BFF. The organisation-frontend calls TenaCare backend; TenaCare backend calls hospital portal + dedan-health APIs (server-to-server with service tokens). This matches the documented "frontend and backend deployed separately" decision in dedan-health.

## 4. How to connect the organisation to receipts and medication coverage (step-by-step)

1. Tag every employee with a dedan_id (import + matching). This is the join key for everything below.
2. Switch hospitals/pharmacies to the credit payer (or a new employer_credit payer) in the hospital portal so their invoices are routed to the employer instead of cash.
3. Enable dispense records in the hospital portal (pharmacist role already exists) so each dispense produces an invoice + receipt file.
4. Add the webhook/polling bridge so TenaCare ingests those invoices as claims.
5. Run the coverage check (org policy + dedan-health insurance) before HR approves — show copay/insurer share on the claim card.
6. Approve in the existing Claims UI -> claim enters the batch.
7. Execute batch in the existing Payments UI -> mark hospital invoices paid.
8. Notify employee via dedan-health inbox ("Your claim for X was approved and paid").

Each step reuses existing UI; the main new work is the TenaCare backend + the bridge.

## 5. Profit and business models

Recommended: hybrid (transaction fees + SaaS + distribution), phased, exactly as dedan-health section 5 recommends but applied to the employer/organisation niche.

Lever | Who pays | How it maps to existing code
SaaS subscription for employers (PEPM) | Employer HR/benefits | TenaCare frontend already is a SaaS shell; add billing via pricing_models.py/billing_system.py from dedan-health
Claims processing fee (2-5% or flat per claim) | Employer or pharmacy | New Claim lifecycle; take fee at settlement
Hospital/pharmacy SaaS (monthly) | Hospital | Hospital portal onboarding + claims module; tiers Basic/Pro/Enterprise
Insurance distribution commission | Insurer (medhinLink etc.) | Cross-sell in employee app; recurring on renewals
Coverage-aware pharmacy fulfilment | Pharmacy partnership | Suggest in-network pharmacies; discounts -> margin
Telehealth revenue share | Scheme/patient | Jitsi visits billed to schemes
Data products (anonymised utilisation) | EHIS/NGOs/researchers | Long-term, needs consent + governance
Premium financing (instalments) | Employee | Financing fee via wallet

Concrete "profit on top of this" angles for an organisation specifically
- Reduce employer medication spend by routing through insurance (CBHI/SHI) first -> org share drops -> you can charge a gain-share fee (% of savings) instead of only a subscription.
- Negotiate pharmacy network discounts as the claims router -> keep a spread.
- Faster settlement for pharmacies (you pay in days, insurer reimburses later) -> charge a small factoring/financing fee.
- Compliance/audit reporting for employers (spend by department, drug class) -> premium SaaS tier.
- Cross-employer: one platform, many employers -> economies of scale.

Unit economics (illustrative, from dedan-health section 5.10)
- Service fee per booking: 5 birr + 2%
- Claims processing fee: 2-5% of claim
- Employer PEPM: per employee per month
- CAC (urban): low (WhatsApp + referrals)
- Retention driver: wallet balance + insurance status + records

## 6. Roadmap (phased, smallest first)

Phase | Scope | Status
0 | Add dedan_id + benefit policy to employee roster; manual claims still work | planned
1 | TenaCare backend (Employee, Claim, BenefitPolicy, auth, audit) | planned
2 | Hospital portal: credit/employer_credit payer + dispense invoices + receipt files | partly exists
3 | Bridge: webhook/polling ingestion hospital -> TenaCare claims | planned
4 | Coverage check: org policy + dedan-health insurance (phases 0-4 of its roadmap) | planned
5 | Auto-notify employees via dedan-health inbox; settlement ref back to hospital | planned
6 | Pharmacy network discounts + gain-share billing | planned
7 | Multi-employer + analytics dashboards | planned

Prerequisites (from dedan-health section 6): auth + audit log are hard blockers before any real deployment of insurance/claims data. Both hospital portal and dedan-health lack production auth today — plan to harden first.

## 7. Risks and constraints

- No auth today in dedan-health and organisation-frontend; hospital portal has staff auth but tokens are simple. Insurance/claims data is sensitive — must harden before go-live.
- EHIS has no public API — CBHI/SHI verification needs a government partnership; until then treat as self-declared with "pending" badge.
- medhinLink is a payout product, not cashless billing — UX must set expectations (patient pays cash, then claims).
- Fraud risk (fake receipts, duplicate claims) — needs verification, audit, and possibly receipt-file hashing (hospital portal already stores sha256).
- Indigent handling — coordinate with woreda offices.
- Regulatory/compliance — data protection, medical liability, insurance distribution licensing; no compliance claims made today.
- Currency/fee sensitivity — keep fees small for the informal sector.

## 8. Recommended first concrete step (lowest risk, highest signal)

Don't build the bridge yet. First, make the organisation-frontend Claims page consume a real claim list from a tiny TenaCare backend that you stand up, seeded with claims copied from the hospital portal's credit-payer invoices. That proves the end-to-end loop (receipt -> verify -> approve -> batch pay) with real data while keeping the existing UI. Then add the webhook and insurance coverage check.

## 9. File/map of where things live

- organisation-frontend: app/(dashboard)/{claims,employees,payments,page}.tsx, components/Sidebar.tsx
- dedan-health insurance design: INSURANCE_TENA_MEDHIN_README.md; backend backend-v2/; billing billing_system.py, pricing_models.py
- hospital portal: backend-hospital/app/models.py (Payer, Patient, ClinicalRecord, RecordFile), app/api/history.py, app/api/imports.py, app/api/patients.py; frontend frontend-hospital-portal/

> Endod/TenaCare provides health education and benefit administration. It is not a substitute for professional medical advice, diagnosis, or treatment. Coverage decisions are made by the relevant scheme/insurer, not by the platform.

