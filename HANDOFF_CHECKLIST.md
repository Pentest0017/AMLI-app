# CISO Assistant — Final Pre-GitHub & Handoff Checklist

This checklist confirms that the codebase is completely sanitized, verified, and ready for push to GitHub and production deployment.

---

## 🔒 PRE-GITHUB AUDIT CHECKLIST

- [x] **Zero Hardcoded Secrets**: No passwords, API keys, JWT secrets, or Microsoft client secrets are committed in source code or docker files.
- [x] **`.gitignore` Enforced**: `.env`, `.venv`, `node_modules`, `*.sqlite3`, build artifacts, and local IDE settings are strictly ignored.
- [x] **`.env.example` Complete**: Fully sectioned template with clear `<PLACEHOLDER>` tags for all application, database, and email variables.
- [x] **Clean-Clone Reproducibility**: Repository contains no absolute local Windows paths (`c:\Users\...`) or external dependencies.
- [x] **Database & Migrations**: All project Django migrations (`0001` through `0190`) are committed, linear, and tested against MSSQL.
- [x] **Production Email Architecture**:
  - `EMAIL_PROVIDER=mailhog` verified for local development.
  - `EMAIL_PROVIDER=microsoft365` verified with safe validation checks for Entra ID credentials.
  - [email_setup_guide.md](file:///c:/Users/alber/OneDrive/Desktop/AMLI_post_check/email_setup_guide.md) and [DEPLOYMENT.md](file:///c:/Users/alber/OneDrive/Desktop/AMLI_post_check/ciso-assistant-community/DEPLOYMENT.md) updated for IT admins.
- [x] **Container Health & Compose**: `docker-compose.yml` updated with environment variable default substitution syntax.
- [x] **Documentation**:
  - [README.md](file:///c:/Users/alber/OneDrive/Desktop/AMLI_post_check/ciso-assistant-community/README.md) updated with architecture, technology stack, local dev, and production setup.
  - [DEPLOYMENT.md](file:///c:/Users/alber/OneDrive/Desktop/AMLI_post_check/ciso-assistant-community/DEPLOYMENT.md) created for IT server administrators.

---

## 🚀 SERVER DEPLOYMENT HANDOFF CHECKLIST

To be executed by Corporate IT / Server Administrator during handoff:

### 1. Repository Setup & Environment
- [ ] Clone repository from GitHub: `git clone <REPO_URL>`.
- [ ] Copy `.env.example` to `.env`: `cp .env.example .env`.
- [ ] Generate a new random `SECRET_KEY` and set `DJANGO_DEBUG=False`.
- [ ] Configure `CISO_ASSISTANT_URL` and `CSRF_TRUSTED_ORIGINS` to match corporate FQDN.

### 2. Database & Storage
- [ ] Provision production Microsoft SQL Server (MSSQL 2019/2022) or use containerized MSSQL service.
- [ ] Configure `DB_PASSWORD` and database user permissions in `.env`.
- [ ] Ensure host persistent storage directory `./db` has `1001:1001` ownership.

### 3. Microsoft 365 Production Email Integration
- [ ] Register Entra ID (Azure AD) Application: `CISO Assistant Platform`.
- [ ] Populate `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`, and `MICROSOFT_CLIENT_SECRET` in `.env`.
- [ ] Grant Exchange Online `SMTP.Send` Application API permission and consent.
- [ ] Enable Authenticated SMTP on `ciso-alerts@yourcompany.com` service mailbox.
- [ ] Set `EMAIL_PROVIDER=microsoft365` in `.env`.

### 4. Stack Launch & Verification
- [ ] Run `docker compose build && docker compose up -d`.
- [ ] Verify container health: `docker compose ps`.
- [ ] Check Huey background worker logs: `docker logs huey`.
- [ ] Perform initial Superuser login via HTTPS.
- [ ] Send test control assignment email to verify Microsoft 365 delivery.
- [ ] Verify PDF report export functionality.
- [ ] Set up automated daily MSSQL database backups.
