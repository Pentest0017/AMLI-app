# Moving the existing database to the Linux server

1. On the Windows SQL Server (172.23.51.190) back up the database (SSMS, or sqlcmd):
   ```sql
   BACKUP DATABASE [ISGRC] TO DISK = N'C:\Backup\ISGRC.bak' WITH COPY_ONLY, INIT, COMPRESSION;
   ```
2. Copy `ISGRC.bak` to the Linux server's home folder (`~`) by USB or scp. **Never commit it to GitHub - it holds your data.**
3. Take `DJANGO_SECRET_KEY` from the current app's `.env`; the restored data (sessions, encrypted fields) needs the same key.
4. Run:
   ```bash
   AMLI_DB_NAME=ISGRC AMLI_SECRET_KEY='<current DJANGO_SECRET_KEY>' bash install.sh
   ```
   `deploy.sh` finds `~/ISGRC.bak` (or `./restore/*.bak`), restores it into the SQL Server container as `ISGRC`, then starts the app.
   Log in with your existing accounts.
