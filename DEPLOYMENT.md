# Production Deployment & Administration Guide

This document is the definitive guide for IT, Exchange, and Infrastructure Administrators deploying **CISO Assistant** into production.

---

## 1. Prerequisites

Before initiating production deployment, ensure the target server and corporate infrastructure meet the following prerequisites:
- A dedicated Linux or Windows server with Docker Engine & Docker Compose V2 installed.
- Administrative access to Microsoft Entra ID (Azure AD) and Microsoft 365 Exchange Online (for production email notifications).
- Access to an enterprise Microsoft SQL Server (MSSQL 2019/2022) or containerized MSSQL instance.
- Public/internal corporate domain name mapped to the server IP address.
- Corporate SSL/TLS certificate or permission to use Let's Encrypt / Caddy internal certificates.

---

## 2. Server Hardware & OS Requirements

| Resource | Minimum Requirement | Recommended Production |
|---|---|---|
| **OS** | Ubuntu 22.04 LTS / Debian 12 / RHEL 9 / Windows Server 2022 | Ubuntu 24.04 LTS / RHEL 9 |
| **CPU** | 2 vCPUs | 4+ vCPUs |
| **RAM** | 4 GB | 8 GB - 16 GB |
| **Disk** | 40 GB SSD | 100 GB+ NVMe / SSD |
| **Network** | Ports 8443 (HTTPS), 80 (HTTP), 1433 (MSSQL) open | Internal firewall rules configured |

---

## 3. Docker Environment Requirements

- **Docker Engine**: Version `24.0.0` or higher
- **Docker Compose**: Version `v2.20.0` or higher
- **Storage Driver**: `overlay2`

Verify installation:
```bash
docker --version
docker compose version
```

---

## 4. Domain & DNS Setup

Create an A or AAAA DNS record in your corporate DNS server:
- **FQDN**: `grc.yourcompany.com` (or `ciso.internal.yourcompany.com`)
- **IP Address**: Target server public/internal IP address.

---

## 5. HTTPS / TLS Certificate Setup

CISO Assistant includes an integrated Caddy reverse proxy that terminates TLS automatically.
- **Option A (Automatic TLS via ACME/Let's Encrypt)**: Ensure port 80 and 443 are reachable from the internet.
- **Option B (Internal CA / Custom Certs)**: Mount custom `.crt` and `.key` files into the Caddy container.
- **Option C (Internal TLS / Self-Signed)**: Default configuration uses internal Caddy TLS (`tls internal`) on port `8443`.

---

## 6. Environment Variables Reference

Copy `.env.example` to `.env` on the server before building:
```bash
cp .env.example .env
```

### Required & Optional Environment Variables

| Variable Name | Purpose | Required? | Example / Placeholder | Where Obtained |
|---|---|---|---|---|
| `CISO_ASSISTANT_URL` | Base HTTPS URL of application | **YES** | `https://grc.yourcompany.com:8443` | Corporate DNS / Domain |
| `ALLOWED_HOSTS` | Allowed Django host headers | **YES** | `grc.yourcompany.com,localhost,backend` | Sysadmin |
| `SECRET_KEY` | Django cryptographic signing key | **YES** | `<GENERATE_STRONG_RANDOM_SECRET_KEY>` | `openssl rand -hex 32` |
| `DJANGO_DEBUG` | Debug mode switch | **YES** | `False` | Set `False` in production |
| `CSRF_TRUSTED_ORIGINS` | Trusted CSRF origins | **YES** | `https://grc.yourcompany.com:8443` | Corporate FQDN |
| `CISO_ASSISTANT_SUPERUSER_EMAIL` | Initial admin account email | **YES** | `admin@yourcompany.com` | Sysadmin choice |
| `CISO_ASSISTANT_SUPERUSER_PASSWORD` | Initial admin account password | **YES** | `<YOUR_SECURE_ADMIN_PASSWORD>` | Sysadmin choice |
| `DB_ENGINE` | Database driver backend | **YES** | `mssql` | Default standard |
| `DB_NAME` | Database name | **YES** | `ciso_assistant_db` | DBA / Sysadmin |
| `DB_USER` | Database username | **YES** | `sa` or `ciso_user` | DBA / Sysadmin |
| `DB_PASSWORD` | Database user password | **YES** | `<YOUR_DB_PASSWORD>` | DBA / Sysadmin |
| `DB_HOST` | Database host | **YES** | `db` (or external MSSQL IP) | Infrastructure team |
| `DB_PORT` | Database port | **YES** | `1433` | Standard MSSQL port |
| `EMAIL_PROVIDER` | Active email channel | **YES** | `microsoft365` | `microsoft365` or `mailhog` |
| `MICROSOFT_TENANT_ID` | Azure AD Directory Tenant ID | Conditional | `<YOUR_TENANT_ID_GUID>` | Entra Admin Center |
| `MICROSOFT_CLIENT_ID` | Azure AD Application Client ID | Conditional | `<YOUR_CLIENT_ID_GUID>` | Entra Admin Center |
| `MICROSOFT_CLIENT_SECRET` | Azure AD Client Secret Value | Conditional | `<YOUR_CLIENT_SECRET_VALUE>` | Entra Admin Center |
| `DEFAULT_FROM_EMAIL` | Sender address | **YES** | `ciso-alerts@yourcompany.com` | Exchange Admin |
| `EMAIL_HOST` | Outbound SMTP server | **YES** | `smtp.office365.com` | Exchange Online default |
| `EMAIL_PORT` | Outbound SMTP port | **YES** | `587` | Standard TLS port |
| `EMAIL_USE_TLS` | Transport security | **YES** | `True` | Standard M365 setting |

---

## 7. MSSQL Database Provisioning & Permissions

If using an external production Microsoft SQL Server:
1. Log into SSMS / SQLCMD as `sysadmin`.
2. Create database and login:
   ```sql
   CREATE DATABASE ciso_assistant_db;
   GO
   CREATE LOGIN ciso_user WITH PASSWORD = '<YOUR_SECURE_PASSWORD>';
   GO
   USE ciso_assistant_db;
   GO
   CREATE USER ciso_user FOR LOGIN ciso_user;
   GO
   ALTER ROLE db_owner ADD MEMBER ciso_user;
   GO
   ```
3. Update `.env` with `DB_HOST=<YOUR_SQL_SERVER_IP>`, `DB_NAME=ciso_assistant_db`, `DB_USER=ciso_user`, `DB_PASSWORD=<YOUR_SECURE_PASSWORD>`.

---

## 8. Django Security Settings Audit

Ensure the following security controls are active in `.env` for production:
```env
DJANGO_DEBUG=False
SECRET_KEY=<SECURE_RANDOM_KEY_AT_LEAST_50_CHARS>
ALLOWED_HOSTS=your-app-domain.com,backend
CSRF_TRUSTED_ORIGINS=https://your-app-domain.com
```

---

## 9. Microsoft 365 Production Email Setup

To connect CISO Assistant to Microsoft 365 via OAuth 2.0 / XOAUTH2:

1. **Entra ID App Registration**:
   - Go to [Entra Admin Center](https://entra.microsoft.com).
   - Register App: `CISO Assistant Platform`.
   - Copy **Directory (tenant) ID** -> `MICROSOFT_TENANT_ID`.
   - Copy **Application (client) ID** -> `MICROSOFT_CLIENT_ID`.
2. **Client Secret**:
   - Go to **Certificates & secrets** -> **+ New client secret**.
   - Copy the secret **Value** -> `MICROSOFT_CLIENT_SECRET`.
3. **API Permissions**:
   - Add permission: Exchange Online -> `SMTP.Send` or `full_access_as_app` (Application Permission).
   - Click **Grant Admin Consent**.
4. **Enable Authenticated SMTP**:
   - Ensure `ciso-alerts@yourcompany.com` mailbox has **Authenticated SMTP** enabled in Microsoft 365 Admin Center.

---

## 10. File & Evidence Storage Volumes

User-uploaded evidence files, custom report templates, and Huey task queues require persistent host storage.

Ensure the host volume mount directory exists and has permissions `1001:1001`:
```bash
mkdir -p ./db
chown -R 1001:1001 ./db
```

In `docker-compose.yml`, persistent data is safely bound to:
- `./db:/code/db` (Huey task queue and SQLite fallback data)
- `mssql_data:/var/opt/mssql` (MSSQL data volume)
- `qdrant_data:/qdrant/storage` (Qdrant vector embeddings volume)

---

## 11. Production Docker Command Sequence

To launch the stack on a clean server:

```bash
# 1. Clone repository
git clone https://github.com/your-org/ciso-assistant-community.git
cd ciso-assistant-community

# 2. Populate production environment variables
cp .env.example .env
nano .env

# 3. Build Docker images
docker compose build

# 4. Start all services in background
docker compose up -d

# 5. Verify service health
docker compose ps

# 6. Apply database migrations (Run automatically on backend boot, or manually):
docker exec backend python manage.py migrate
```

---

## 12. Background Worker Verification (Huey)

Verify Huey worker status:
```bash
docker logs -f huey
```
*Expected log:* `[EscalationEngine] Automated escalation background worker started.`

---

## 13. Caddy Reverse Proxy & Routing

Caddy routes incoming requests:
- `https://your-domain:8443/api/*` -> `backend:8000`
- `https://your-domain:8443/*` -> `frontend:3000`

Inspect Caddy logs:
```bash
docker logs -f caddy
```

---

## 14. Initial Admin Account & Application Setup

1. Open `https://<YOUR_DOMAIN>:8443` in browser.
2. Sign in with `CISO_ASSISTANT_SUPERUSER_EMAIL` and `CISO_ASSISTANT_SUPERUSER_PASSWORD`.
3. Go to **System** -> **Report Templates** / **Email Templates** to customize organization branding if desired.
4. Invite initial users and assign platform roles (**Admin**, **Auditor**, **Auditee**).

---

## 15. Production Deployment Checklist

- [ ] `.env` created from `.env.example` with real production values.
- [ ] `SECRET_KEY` generated randomly.
- [ ] `DJANGO_DEBUG=False` set.
- [ ] MSSQL database reachable and healthy.
- [ ] Docker compose containers running and healthy (`backend`, `frontend`, `db`, `huey`, `qdrant`, `caddy`).
- [ ] HTTPS URL loads cleanly in browser without SSL errors.
- [ ] Initial Superuser login successful.
- [ ] Control assignment email notification tested.
- [ ] Defaulters escalation engine verified.
- [ ] Report generation PDF export verified.
- [ ] Automated database backup cron job configured.

---

## 16. Backup & Disaster Recovery

### Database Backup (MSSQL)
Configure a daily automated backup of the MSSQL database:
```bash
docker exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P '<YOUR_DB_PASSWORD>' -C -Q "BACKUP DATABASE master TO DISK = '/var/opt/mssql/data/ciso_backup.bak' WITH FORMAT;"
```

### Media & Config Backup
Back up the `./db` folder and `.env` file daily:
```bash
tar -czvf ciso_config_backup_$(date +%F).tar.gz ./db .env
```

---

## 17. Troubleshooting Guide

| Symptom | Cause | Resolution |
|---|---|---|
| `backend` container unhealthy | MSSQL not ready on boot | `docker compose restart backend` after `db` container becomes healthy. |
| Microsoft 365 emails fail | Missing Entra credentials or SMTP disabled | Check `MICROSOFT_TENANT_ID`, `CLIENT_ID`, `CLIENT_SECRET` in `.env` and verify SMTP Auth on service mailbox. |
| CSRF Verification Failed | Host not in `CSRF_TRUSTED_ORIGINS` | Add `https://<YOUR_DOMAIN>` to `CSRF_TRUSTED_ORIGINS` in `.env`. |
| Database connection refused | Incorrect DB host or password | Verify `DB_HOST=db` and `DB_PASSWORD` matches `MSSQL_SA_PASSWORD`. |
