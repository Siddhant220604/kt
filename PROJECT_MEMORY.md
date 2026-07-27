# Kiran Traders — Project Memory

_Last updated: 2026-07-15_

## What This Is
A full B2B wholesale e-commerce web platform built for **Kiran Traders**, a Lucknow-based
wholesaler of thermocol, plastic bags, and disposable items, established 2004. Includes a
public storefront and a full admin panel. No online payment gateway is currently live
(manual payment methods only: COD / UPI / Bank Transfer); no outbound email is used —
customer/order notifications go over WhatsApp Cloud API instead.

## Business Info
- Name: Kiran Traders (est. 2004)
- Address: 253/121, Below Jaiswal Dharamshala, Nehru Cross, Nadan Mahal Road, Lucknow – 226004, UP
- Phones: +91 9044057739 / +91 9044097739
- Hours: Mon–Wed, Fri–Sun 10AM–8PM; closed Thursdays

## Tech Stack
- **Backend**: FastAPI (Python) + MongoDB via Motor (async driver) + JWT auth
  + Pillow (images) + qrcode + reportlab (PDF invoices)
- **Frontend**: React 19 (Create React App + Craco) + Tailwind CSS + Framer Motion
  + shadcn/ui (Radix primitives) + lucide-react icons + React Router 7
  + TanStack React Query / SWR for data fetching + react-hook-form + recharts (admin charts)
- **Infra**: Docker Compose setup with three services — `mongo` (Mongo 7.0), `backend`
  (FastAPI, port 8000), `frontend` (built React app served via nginx, port 3000→80).
  Backend and frontend each have their own Dockerfile.
- **Notifications**: WhatsApp Cloud API (Meta) — no SMTP/email integration exists.
- **Payments**: Razorpay integration code exists in the repo/tests but is currently
  deferred/not the active checkout path — active checkout flow is COD / UPI / Bank
  Transfer collected manually. Order tracking is by Order ID + mobile number.

## Repository Layout
```
backend/
  server.py            main FastAPI app / routes
  auth.py               auth logic
  security.py           security helpers
  audit.py               audit logging
  dependencies.py        shared FastAPI dependencies
  config/
    rate_limits.py        tiered rate limiting config
    whatsapp.py            WhatsApp config
  services/
    whatsapp_service.py    WhatsApp Cloud API integration
  tests/                  pytest suite (order notifications, rate limits, razorpay, whatsapp lifecycle)
  backend_test.py
  Dockerfile, requirements.txt, runtime.txt, pytest.ini

frontend/
  src/
    App.js, App.css, index.js, index.css
    components/            shared UI (AdminLayout, ProtectedRoute, CustomerProtectedRoute,
                            PublicLayout, ProductCard, ErrorBoundary, site/, ui/)
    pages/                 About, Account, Cart, Checkout, Contact, Home, NotFound,
                            OrderSuccess, OrderTracking, ProductDetail, Products, SignIn, SignUp, Wishlist
    pages/admin/            AuditLog, Banners, Categories, Contacts, Coupons, Customers,
                            Dashboard, Login, OrderDetail, Orders, Products, Profile, Reviews, Settings
    lib/                    api.js, cart.js, settings.js, theme.js, utils.js, wishlist.js
    hooks/, constants/testIds/
  Dockerfile, nginx.conf, craco.config.js, tailwind.config.js, components.json, vercel.json

docker-compose.yml       mongo + backend + frontend services
.env.example              template for required env vars (no real secrets)
design_guidelines.json    UI/design system guidelines
memory/PRD.md              condensed product requirements doc (pre-existing memory file)
test_result.md             yaml-in-markdown testing protocol/log shared between main & testing agents
tests/                     top-level test dir
test_reports/               iteration test run reports (e.g. iteration_2.json)
```

## Environment Variables (names only, no values — see `.env.example`)
- `MONGO_URL`, `DB_NAME`, `FRONTEND_URL`
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`
- `WHATSAPP_DEFAULT_COUNTRY_CODE`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
  `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_API_VERSION`
- `GOOGLE_REVIEW_LINK`, `REVIEW_REQUEST_DELAY_SECONDS`
- `REACT_APP_BACKEND_URL` (frontend build-time API URL)

## Admin Panel Features
Orders, Products, Categories, Customers, Banners, Coupons, Reviews, Contacts, Settings,
Audit Log, Profile, Dashboard — reachable under `frontend/src/pages/admin/`.

## Customer-Facing Features
Storefront browsing (Home/Products/ProductDetail), Cart, Checkout (COD/UPI/Bank Transfer),
Order Tracking by Order ID + mobile, account sign-in/sign-up (email/password — OTP login was
replaced), Wishlist, Contact page, About page.

## Notable History / Evolution (from git log, newest first)
- Reworked WhatsApp order lifecycle notifications for newly approved Meta templates; fixed
  out-for-delivery template name.
- Removed obsolete invoice and Razorpay documentation files; removed Emergent platform
  metadata from the repo (now ignores `.emergent/`).
- Added Docker Compose setup with Dockerfiles for backend and frontend (containerized deploy).
- Hardened error handling, added WhatsApp delivery diagnostics, validated image upload content.
- Fixed WhatsApp template params, gated invoice download behind conditions, added invoice
  numbers, tightened input validation, updated dependencies.
- Added tiered/configurable rate limiting with auth backoff (replacing hard lockouts).
- Migrated WhatsApp notifications to Meta's approved template system; enforced account
  uniqueness; assorted UX fixes.
- Prevented browsers from autofilling admin credentials into customer-facing forms.
- Replaced OTP-based customer login with email/password accounts; sign-in now required
  before checkout.
- Fixed a batch of security/correctness bugs; added audit log, low-stock alerts, tiered
  pricing, abandoned-cart nudges, customer OTP login (later replaced), refund tracking.
- Multiple rounds of Razorpay Standard Checkout integration work (UPI enablement, 401 error
  debugging) — this payment path appears to have since been de-scoped/deferred in favor of
  manual payment methods.
- Redesigned invoice PDF template to match the physical invoice book layout, GST-compliant format.
- Added data integrity guards, caching, performance and hardening pass.
- Added order/stock correctness fixes, abuse protection, CI pipeline, CSV export, SEO improvements.
- Removed manual UPI/bank transfer options at one point, then later these became the primary
  payment methods again once Razorpay was deferred.
- Renamed order status "shipped" → "out for delivery" for clarity.

## Known Deferred / Backlog Items (from `memory/PRD.md`)
- P1: Razorpay online payments — explicitly skipped per user decision (manual payments only for now)
- P1: Email/SMTP order confirmations — explicitly skipped per user decision (WhatsApp used instead)
- P2: PWA install manifest
- P2: PDF invoice email delivery
- P2: WhatsApp broadcast for order status updates

## Testing
- Backend: pytest suite in `backend/tests/` (`conftest.py`, `test_order_notifications.py`,
  `test_rate_limits.py`, `test_razorpay.py`, `test_whatsapp_lifecycle_features.py`) plus
  `backend/backend_test.py`.
- `test_result.md` at repo root implements a structured "testing protocol" — a YAML-in-Markdown
  log shared between the main coding agent and a separate testing agent, tracking per-task
  `implemented`/`working`/`stuck_count`/`priority` status for both backend and frontend, plus
  a running `agent_communication` log. This file must retain its protocol header section
  verbatim per its own embedded instructions.
- `test_reports/` holds historical iteration run output (e.g. `iteration_2.json`), which
  previously passed with no failures across backend + frontend flows.

## CI / Tooling
- `.github/workflows/` — GitHub Actions CI configured (exact jobs not detailed here; check
  the workflow files directly for current CI steps).
- `.claude/settings.local.json` — local Claude Code permission settings for this repo.
- `design_guidelines.json` — structured design-system rules (colors, spacing, components)
  used to keep the storefront/admin UI consistent.

## Notes on Prior Deployment Platform
The repo previously carried "Emergent" platform metadata (build/deploy artifacts from an
earlier hosting/build tool called Emergent) which has since been removed and is now
gitignored (`.emergent/`). The project has moved to a self-hosted Docker Compose deployment
model (Mongo + FastAPI backend + nginx-served React frontend).
