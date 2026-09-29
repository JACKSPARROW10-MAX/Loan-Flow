# LoanFlow – Digital Loan Origination, Approval & Servicing Platform

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Next.js%20%7C%20Supabase-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

LoanFlow is an enterprise digital lending platform designed to replace paper-heavy banking loan operations with a unified digital workflow: **Application → KYC Verification → Document Verification → Explainable Eligibility Rules → Risk Scoring → Limit Calculation → Automated Assessment Report → Maker-Checker Manager Approval → Servicing & Repayments → Delinquency & Collection → Executive Portfolio Analytics**.

---

## 🎨 Visual Design & Palette

Built with modern fintech aesthetics adhering to the design specifications:
- **Pine / Forest Green** (`#0C3B2E`): Primary brand, executive header, and authority elements.
- **Sage Green** (`#6D9773`): Secondary accents, verified document badges, and approval states.
- **Warm Ochre / Camel** (`#BB8A52`): Tertiary badges, limit indicators, and document borders.
- **Warm Gold / Amber** (`#FFBA00`): Highlights, buttons, and alert callouts.
- **Canvas Cream** (`#F7F8F5`): Warm, elegant background surface.

---

## 🏗️ Architecture & Tech Stack

```
Loan-Flow/
├── frontend/                     # Next.js 16 (React 19 + TypeScript + Tailwind CSS v4)
│   ├── src/app/                  # App Router & Layouts
│   ├── src/components/           # Customer Portal, Underwriter Workbench, Manager Desk, Analytics
│   ├── src/types/                # TypeScript data models
│   └── src/lib/                  # API client & mock data
├── services/                     # Python 3.11+ FastAPI Microservices
│   ├── gateway/                  # Central API Gateway (CORS, Rate Limiting, Security Headers)
│   ├── auth/                     # Authentication & RBAC (httpOnly JWT, CSRF Protection)
│   ├── loan_app/                 # Loan Origination, State Machine, Servicing, Collection, Audit
│   ├── mock_kyc/                 # Mock Bureau & UIDAI/PAN Verification API
│   ├── risk/                     # ML Credit Risk Scoring Engine (Scikit-Learn/Numpy)
│   ├── document/                 # Document Management & Signed Storage
│   ├── audit/                    # Append-Only Event Bus & Audit Consumer
│   └── shared/                   # Shared DB session, Supabase storage, Security & Config
├── tests/                        # Comprehensive Pytest Suite
│   └── test_loanflow.py          # End-to-end integration tests & maker-checker enforcement
├── docker-compose.yml            # Full-stack containerized local development
├── render.yaml                   # Render Cloud Blueprint for backend services
└── .env.example                  # Environment configuration template
```

---

## ✨ Key Features & Innovations

### 1. Unified Digital Journey & Live Stepper
Customers apply online and track their application in real time across the complete state machine:
`Draft → Submitted → KYC → Docs → Verification → Risk → Prepared → With Manager → Approved / Servicing`.

### 2. Sensitive KYC Field Masking
Aadhaar, PAN, and phone numbers are securely masked (e.g. `********9012`, `******234F`), ensuring borrower privacy compliance while maintaining verifiable records.

### 3. Duplicate Document Detection (SHA-256)
Every uploaded document is scanned and hashed. If duplicate content is detected across applications, the system immediately rejects the upload with an HTTP 409 Conflict.

### 4. Explainable Policy & Eligibility Engine
Policy rules (Min Income, Max Debt-to-Income / EMI ratio, Employment type, Maximum loan ceiling) return unambiguous pass/fail reasons saved directly to the file dossier.

### 5. Credit Risk Scoring & Permissible Limit Calculation
Automated risk scoring model evaluates financial stability and assigns applicants to Risk Bands (Low, Medium, High, Very High). The permissible limit calculator applies product-specific income multiples and subtracts existing debt obligations.

### 6. Enforced Maker-Checker Segregation
- The Underwriter who prepares the file (`prepared_by`) is cryptographically and logically blocked from approving it (HTTP 403 Forbidden).
- Only distinct users with `role="manager"` (`approved_by`) can sanction, return, or reject loans.

### 7. Automated Assessment Report Dossier
Consolidates borrower details, masked KYC checks, verified document hashes, explainable rule outcomes, risk scores, and audit trails into a single dossier for credit committee review.

### 8. Servicing & Reducing-Balance EMI Amortization
Upon manager sanction, 1-click disbursement creates an active loan account and generates an amortization schedule. Customers can simulate instant repayments (UPI / NetBanking), which updates schedules and outstanding balances in real time.

### 9. Delinquency Monitoring & Collection Desk
Loans are categorized by Days Past Due into regulatory aging buckets:
- **1–30 DPD** (SMA-0)
- **31–60 DPD** (SMA-1)
- **61–90 DPD** (SMA-2)
- **90+ DPD** (NPA - Non-Performing Asset)
Officers can log recovery notes and schedule follow-ups.

### 10. Immutable Audit Trail
All actions (stage changes, rule executions, document verifications, disbursements, payments) are logged. An automated PostgreSQL trigger permanently blocks `UPDATE` and `DELETE` operations on `audit_log`.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) Docker & Docker Compose

### 1. Environment Setup
Copy the template and configure your Supabase and Redis credentials:
```bash
cp .env.example .env
```

### 2. Running Automated Tests
Run the test suite covering the full loan lifecycle, maker-checker rule, document deduplication, and servicing:
```bash
pytest tests/test_loanflow.py -v -W ignore
```

### 3. Running with Docker Compose
To start all services and the Next.js frontend together:
```bash
docker compose up --build
```
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **API Gateway**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Running Frontend Locally
```bash
cd frontend
npm install
npm run dev
```

---

## ☁️ Deployment

- **Database & Storage**: [Supabase](https://supabase.com) (PostgreSQL + Supabase Storage for files).
- **Cache**: [Upstash](https://upstash.com) (Serverless Redis).
- **Backend Services**: Deploy via `render.yaml` blueprint to [Render](https://render.com).
- **Frontend UI**: Deploy `frontend/` directory directly to [Vercel](https://vercel.com).