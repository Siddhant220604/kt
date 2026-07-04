# Kiran Traders — B2B Wholesale Website

## Original Problem
B2B web platform for Kiran Traders (est. 2004, Lucknow) — wholesaler of thermocol/plastic bags/disposable items. Full storefront + admin panel. Payments manual only (COD/UPI/Bank Transfer). No email, no AI.

## Business Info
- Name: Kiran Traders (Since 2004)
- Address: 253/121, Below Jaiswal Dharamshala, Nehru Cross, Nadan Mahal Road, Lucknow – 226004, UP
- Phones: +91 9044057739 / +91 9044097739
- Hours: Mon-Wed, Fri-Sun 10AM–8PM, Thursday closed
- Admin: admin@kirantraders.com / Admin@123

## Tech Stack
- Backend: FastAPI + MongoDB (Motor) + JWT auth + Pillow/qrcode/reportlab
- Frontend: React (CRA + Craco) + Tailwind + Framer Motion + shadcn/ui + lucide-react
- Object Storage: Emergent Object Storage (available if needed for uploads)

## What's Been Implemented (2026-07-04)
- Full Kiran Traders codebase deployed from user's uploaded zip
- Content edits per user: About story rewritten; Home trust bar shows 10K+ Orders / Fast Delivery / Fast Dispatch / 5.0 Rating (dropped "10000+ products")
- Backend seeded: 1 admin, 7 categories, sample products, banners, coupons, settings
- COD / UPI / Bank Transfer checkout flow, order tracking by ID+mobile
- Admin dashboard with Orders/Products/Categories/Customers/Banners/Coupons/Reviews/Contacts/Settings

## Verified
- Testing agent iteration_2.json passed with no failures on backend + frontend flows.

## Backlog (deferred)
- P1: Razorpay online payments (skipped per user)
- P1: Email/SMTP order confirmations (skipped per user)
- P2: PWA install manifest, PDF invoice email delivery
- P2: WhatsApp broadcast for order status updates
