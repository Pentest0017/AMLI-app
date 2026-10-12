# AMLI — Automated Management & Compliance Platform

**AMLI** (Automated Management & Compliance Platform) is an enterprise-grade Governance, Risk, and Compliance (**GRC**) and Intermediary Compliance management solution. Designed for corporate environments, AMLI connects compliance frameworks, risk scenarios, control assignments, automated escalations, and custom PDF report generation into a single unified platform.

---

## 🌟 Key Features & Capabilities

### 🛡️ 1. Intermediary Compliance & Business Function Tracking
- Comprehensive tracking of assigned business functions and intermediary compliance status.
- Centralized evidence repository for evidence submission, review, and status tracking.
- Dedicated compliance summary dashboards for real-time progress monitoring.

### 📋 2. Control Assignment & Intelligent Email Batching
- Assign applied controls to owners with explicit due dates and grace period options.
- **Automated 4-Hour Email Batching Window**: Consolidates assignment notifications to prevent user inbox spamming while ensuring timely delivery.
- Direct quick-action links in emails for seamless evidence submission.

### ⏰ 3. Automated L1 / L2 / L3 Escalation Engine & Defaulters Tracker
- **Multi-Level Escalation**:
  - **L1 Reminder**: Dispatched on or around the due date.
  - **L2 Warning**: Triggered after L1 with configurable grace periods.
  - **L3 Final Escalation**: Triggered after L2 grace period expires.
- **Defaulters Tracker**: Centralized dashboard to track overdue controls, pending evidence, and escalation history.

### 📄 4. Custom Report & Template Generation
- **System > Report Templates**: Configurable HTML, Word, and PDF report templates.
- One-click PDF audit report generation matching custom corporate templates for both **Compliance Summary** and **Intermediary Compliance**.
- Supports custom headers, organization branding, logos, and structured requirement summaries.

### 📧 5. Enterprise Microsoft 365 / Exchange Online Integration
- **Dual-Mode Email Provider Architecture**:
  - `EMAIL_PROVIDER=mailhog` for instant local development & testing.
  - `EMAIL_PROVIDER=microsoft365` for corporate deployment using **Modern Authentication (OAuth 2.0 / XOAUTH2)** via Microsoft Entra ID (Azure AD).
- Zero plaintext credentials exposed; safe environment variable injection.

### 🔐 6. Granular RBAC & Web Feature Matrix
- Strict Role-Based Access Control (**Admin**, **Auditor**, **Auditee**).
- Feature Matrix integration dynamically hides disabled modules from the navigation sidebar and enforces server-side permission checks.

---

## 🏗️ Architecture & Technology Stack

- **Frontend**: SvelteKit, TypeScript, TailwindCSS, Skeleton UI.
- **Backend API**: Django 4.2 REST Framework, Python 3.14, structlog.
- **Database**: Microsoft SQL Server 2022 (MSSQL) / PostgreSQL / SQLite.
- **Background Task Worker**: Huey (SqliteHuey background scheduler).
- **Reverse Proxy / TLS**: Caddy Server with automated internal/ACME TLS termination.
- **Vector Search / RAG**: Qdrant Vector Database.

---

## 🚀 Deployment & Environment Setup

### 1. Prerequisites
- Docker Engine `v24.0.0+` & Docker Compose V2 `v2.20.0+`.
- Microsoft SQL Server 2019/2022 or containerized MSSQL.

### 2. Environment Configuration
Copy `.env.example` to `.env` and populate your environment settings:
```bash
cp .env.example .env
```

Key environment variables:
```env
# Application URL
CISO_ASSISTANT_URL=https://grc.yourcompany.com:8443
ALLOWED_HOSTS=grc.yourcompany.com,localhost,backend

# Database Configuration (MSSQL)
DB_ENGINE=mssql
DB_NAME=ciso_db
DB_USER=sa
DB_PASSWORD=<YOUR_SECURE_PASSWORD>
DB_HOST=db

# Production Microsoft 365 Email Settings
EMAIL_PROVIDER=microsoft365
MICROSOFT_TENANT_ID=<YOUR_TENANT_ID>
MICROSOFT_CLIENT_ID=<YOUR_CLIENT_ID>
MICROSOFT_CLIENT_SECRET=<YOUR_CLIENT_SECRET>
DEFAULT_FROM_EMAIL=ciso-alerts@yourcompany.com
```

### 3. Docker Launch Sequence
```bash
# Build and start all services
docker compose build
docker compose up -d

# Verify container health
docker compose ps
```

---

## 📚 Documentation Reference

- [DEPLOYMENT.md](DEPLOYMENT.md): Detailed Production Server & Database Setup Guide for Administrators.
- [HANDOFF_CHECKLIST.md](HANDOFF_CHECKLIST.md): Pre-flight verification checklist for handoff and deployment.
- [email_setup_guide.md](../email_setup_guide.md): Step-by-step Microsoft Entra ID & Exchange Online configuration guide.

---

## 📄 License
This project is licensed under the AGPL-3.0 License.
